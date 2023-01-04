import base64
import io
import json
import logging
from datetime import datetime
from multiprocessing.pool import ThreadPool

import graphene
import reversion
from django.core.files import File
from django.db import transaction
from django.db.models import Q

import organization.errors as errors
from action_item.models import ActionItem
from address.models import Address
from dashboard.types import ActionItemTypeV2
from laika.auth import login_required, permission_required
from laika.decorators import concierge_service, laika_service
from laika.types import ErrorType
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.exceptions import ServiceException
from laika.utils.history import create_revision
from laika.utils.permissions import map_permissions
from organization.calendly.rest_client import validate_event
from organization.constants import STATES
from organization.constants import TIERS as ORG_TIERS
from organization.constants import (
    compliance_architect_user,
    contract_sign_date,
    customer_success_manager_user,
)
from pentest.typeform.rest_client import get_typeform_answer_from_response
from tag.models import Tag
from tag.types import TagType
from user.models import User
from user.tasks import process_invite_onboarding_users
from user.utils.action_items import create_quickstart_action_items
from user.utils.invite_laika_user import invite_user_m
from user.utils.user_model_query import find_user_by_id_type

from .constants import ACTIVE_STATE, COMPLETED_STATE
from .inputs import (
    CreateOrganizationCheckInInput,
    DeleteOrganizationCheckInInput,
    LocationInput,
    MoveOrgOutOfOnboardingInput,
    OnboardingStepCompletionInput,
    OrganizationByIdInput,
    OrganizationInput,
    UpdateLocationInput,
    UpdateOnboardingInput,
)
from .models import (
    ONBOARDING,
    PREMIUM,
    ApiTokenHistory,
    CheckIn,
    OffboardingStatus,
    OffboardingVendor,
    Onboarding,
    OnboardingResponse,
    OnboardingSetupStep,
    Organization,
    OrganizationChecklist,
    OrganizationChecklistRun,
    OrganizationChecklistRunSteps,
    OrganizationLocation,
)
from .tasks import (
    create_organization_seed,
    create_super_admin_users,
    create_super_user_and_invite,
    process_organization_vendors,
    tddq_execution,
)
from .types import (
    ONBOARDING_TYPEFORM_FORM,
    CheckListStepType,
    OnboardingResponseType,
    OrganizationChecklistRunResourceType,
    OrganizationChecklistRunType,
    OrganizationType,
    SetupStepType,
)
from .utils.api_token_generator import generate_api_token

logger = logging.getLogger('Organization')
pool = ThreadPool()

ORG_EXISTS_MESSAGE = 'Organization name already exists'


class UpdateOnboarding(graphene.Mutation):
    class Arguments:
        input = UpdateOnboardingInput(required=True)

    id = graphene.Int()
    state = graphene.String()

    @staticmethod
    @laika_service(
        permission='organization.change_onboarding',
        exception_msg='Failed to update onboarding. Please try again',
        revision_name='Update onboarding',
    )
    def mutate(self, info, **kwargs):
        organization = info.context.user.organization
        org_onboarding = Onboarding.objects.get(organization=organization)
        kwargs['input'].to_model(update=org_onboarding, save=False)
        org_onboarding.save(current_user=info.context.user)
        return UpdateOnboarding(id=org_onboarding.id, state=org_onboarding.state)


# This method will be deprecated in favor of CompleteOnboarding
# when onboarding V2 is released
class InviteAndCompleteOnboarding(graphene.Mutation):
    class Arguments:
        input = graphene.List(graphene.String, required=True)

    invited_users = graphene.List(graphene.String)

    @staticmethod
    @laika_service(
        permission='user.add_user',
        exception_msg=(
            'Failed to invite users and complete onboarding. Please try again'
        ),
        revision_name='Invite users',
    )
    def mutate(self, info, **kwargs):
        users_id = []
        organization = info.context.user.organization
        emails_to_invite = kwargs['input']

        users = User.objects.filter(
            organization=organization, is_active=False, email__in=emails_to_invite
        )
        for user in users:
            invitation_data = invite_user_m(info, vars(user))
            user_created = invitation_data['data']
            users_id.append(user_created.id)
            create_quickstart_action_items(user_created)

        organization.state = ACTIVE_STATE
        organization.save()

        onboarding = organization.onboarding.first()
        onboarding.state = COMPLETED_STATE
        onboarding.save()

        return InviteAndCompleteOnboarding(invited_users=users_id)


class CreateLocation(graphene.Mutation):
    class Arguments:
        input = LocationInput(required=True)

    id = graphene.Int()

    @staticmethod
    @laika_service(
        permission='organization.add_organizationlocation',
        exception_msg='Failed to create location. Please try again',
        revision_name='Create location',
    )
    def mutate(self, info, **kwargs):
        organization = info.context.user.organization
        location_input = kwargs['input']
        address = Address.objects.create(
            street1=location_input.get('street1', ''),
            street2=location_input.get('street2', ''),
            city=location_input.get('city', ''),
            country=location_input.get('country', ''),
            state=location_input.get('state', ''),
            zip_code=location_input.get('zip_code', ''),
        )

        OrganizationLocation.objects.create(
            organization=organization,
            address=address,
            hq=location_input.get('hq', False),
            name=location_input.get('name'),
        )
        return CreateLocation(id=address.id)


class UpdateLocation(graphene.Mutation):
    class Arguments:
        input = UpdateLocationInput(required=True)

    id = graphene.Int()

    @staticmethod
    @laika_service(
        permission='organization.change_organizationlocation',
        exception_msg='Failed to update location. Please try again',
        revision_name='Update location',
    )
    def mutate(self, info, **kwargs):
        organization = info.context.user.organization
        location_input = kwargs['input']
        address = Address.objects.get(id=location_input.id)
        org_location = OrganizationLocation.objects.get(
            organization=organization, address=address
        )

        location_input.to_model(update=address)

        name = location_input.get('name')
        hq = location_input.get('hq')

        if name:
            org_location.name = name

        if hq is not None:
            org_location.hq = hq

        org_location.save()

        return UpdateLocation(id=address.id)


class DeleteLocation(graphene.Mutation):
    class Arguments:
        input = graphene.List(graphene.Int, required=True)

    deleted = graphene.List(graphene.Int)

    @staticmethod
    @laika_service(
        permission='organization.delete_organizationlocation',
        exception_msg='Failed to delete location. Please try again',
        revision_name='Delete location',
    )
    def mutate(self, info, **kwargs):
        organization = info.context.user.organization
        ids_to_delete = kwargs['input']

        Address.objects.filter(
            id__in=ids_to_delete, organization_location__organization=organization
        ).delete()

        has_hq = OrganizationLocation.objects.filter(
            organization=organization, hq=True
        ).exists()

        next_location = OrganizationLocation.objects.filter(
            organization=organization
        ).first()

        if not has_hq and next_location:
            next_location.hq = True
            next_location.save()

        return DeleteLocation(deleted=ids_to_delete)


class CreateOrganization(graphene.Mutation):
    class Arguments:
        input = OrganizationInput(required=True)

    success = graphene.Boolean()
    error = graphene.Field(ErrorType)
    organization = graphene.Field(OrganizationType)

    @staticmethod
    @concierge_service(
        permission='organization.add_organization',
        exception_msg='Failed to create organization',
        revision_name='Organization created',
    )
    def mutate(self, info, input=None):
        organization_name = input.get('name').strip()
        organization_website = input.get('website')

        if Organization.objects.filter(name__iexact=organization_name).first():
            raise ServiceException(ORG_EXISTS_MESSAGE)

        if Organization.objects.filter(website=organization_website).first():
            raise ServiceException('Organization website already exists')

        organization = create_organization_from_payload(input, info)
        set_ca_and_csm(organization, input)
        set_logo(organization, input)
        create_super_admin_users(organization)
        create_organization_seed(organization, info.context.user)

        return CreateOrganization(success=True, error=None, organization=organization)


def create_organization_from_payload(payload, info):
    return Organization.objects.create(
        **exclude_dict_keys(
            payload,
            [
                'billing_address',
                'file_name',
                'file_contents',
                'customer_success_manager',
                'compliance_architect',
            ],
        ),
        tier=ORG_TIERS.get(PREMIUM),
        state=STATES.get(ONBOARDING),
        created_by=info.context.user,
    )


def set_ca_and_csm(organization: Organization, payload: dict):
    try:
        csm = payload.get('customer_success_manager')
        if csm and csm.email:
            organization.customer_success_manager_user = User.objects.get(
                email=csm.email
            )

        ca = payload.get('compliance_architect')
        if ca and ca.email:
            organization.compliance_architect_user = User.objects.get(email=ca.email)

        organization.save()
    except Exception as e:
        logger.warning(f'Error when creating new organization: {e}')
        raise ServiceException('Error setting CSM or CA for new organization')


def set_logo(organization: Organization, payload: dict):
    file_name = payload.get('file_name')
    file_contents = payload.get('file_contents')

    if not file_name or not file_contents:
        return None

    logo = File(
        name=file_name,
        file=(io.BytesIO(base64.b64decode(file_contents))),  # type: ignore
    )

    organization.logo = logo
    organization.save()


class UpdateOrganization(graphene.Mutation):
    class Arguments:
        input = OrganizationInput(required=True)

    success = graphene.Boolean()
    error = graphene.Field(ErrorType)
    data = graphene.Field(OrganizationType)
    permissions = graphene.List(graphene.String)

    @staticmethod
    @login_required
    @permission_required('organization.change_organization')
    @create_revision('Updated organization')
    def mutate(self, info, input=None):
        success = True
        error = None
        permissions = None
        try:
            with transaction.atomic():
                organization = info.context.user.organization
                current_user = info.context.user

                new_address = input.get('billing_address')
                if new_address:
                    address = organization.billing_address
                    Address.objects.update_or_create(
                        id=address.id, defaults={**new_address}
                    )

                if input.file_name is not None and input.file_contents is not None:
                    organization.logo = File(
                        name=input.file_name,
                        file=(
                            io.BytesIO(base64.b64decode(input.file_contents))
                            if input.file_contents
                            else ""
                        ),
                    )
                    organization.save()

                Organization.objects.filter(id=organization.id).update(
                    **exclude_dict_keys(
                        input, ['billing_address', 'file_name', 'file_contents']
                    )
                )

                data = Organization.objects.get(id=organization.id)

                permissions = map_permissions(current_user, 'organization')

                return UpdateOrganization(
                    success=success, error=error, data=data, permissions=permissions
                )
        except Exception:
            logger.exception(errors.MISSING_REQUIRED_FIELDS)
            error = errors.UPDATE_ORG_ERROR

            return UpdateOrganization(
                success=False, error=error, data=None, permissions=permissions
            )


def is_duplicate_name(organization_id: str, payload: dict):
    name = payload.get('name')
    if (
        name
        and Organization.objects.filter(
            Q(name__iexact=name) & ~Q(id=organization_id)
        ).exists()
    ):
        return True
    else:
        return False


def update_organization_base_details(
    organization_id: str, payload: dict
) -> Organization:
    payload['updated_at'] = datetime.now()
    Organization.objects.filter(id=organization_id).update(
        **exclude_dict_keys(
            payload,
            [
                'id',
                'file_name',
                'file_contents',
                'customer_success_manager_user',
                'compliance_architect_user',
                'contract_sign_date',
            ],
        )
    )

    return Organization.objects.get(id=organization_id)


def update_csm_user(organization, payload):
    if customer_success_manager_user not in payload.keys():
        return

    csm = payload.get(customer_success_manager_user)
    try:
        csm_user = User.objects.get(email=csm.email) if csm and csm.email else None

        if csm_user != organization.customer_success_manager_user:
            logger.info(
                f'Updating CSM user for organization {organization}. Payload: {payload}'
            )
            organization.customer_success_manager_user = csm_user
            organization.save()

            if csm_user:
                create_super_user_and_invite(
                    organization,
                    {
                        'email': csm_user.email,
                        'first_name': csm_user.first_name,
                        'last_name': csm_user.last_name,
                        'organization_id': organization.id,
                    },
                )
    except Exception as e:
        logger.warning(f'Error updating CSM user: {e}')


def update_ca_user(organization, payload):
    if compliance_architect_user not in payload.keys():
        return

    ca = payload.get(compliance_architect_user)
    try:
        ca_user = User.objects.get(email=ca.email) if ca and ca.email else None

        if ca_user != organization.compliance_architect_user:
            logger.info(
                f'Updating CA user for organization {organization}. Payload: {payload}'
            )
            organization.compliance_architect_user = ca_user
            organization.save()

            if ca_user:
                create_super_user_and_invite(
                    organization,
                    {
                        'email': ca_user.email,
                        'first_name': ca_user.first_name,
                        'last_name': ca_user.last_name,
                        'organization_id': organization.id,
                    },
                )
    except Exception as e:
        logger.warning(f'Error updating CA user: {e}')


class UpdateOrganizationById(graphene.Mutation):
    class Arguments:
        input = OrganizationByIdInput(required=True)

    data = graphene.Field(OrganizationType)

    @concierge_service(
        permission='user.change_concierge',
        exception_msg='Failed to update organization',
        revision_name='Details updated',
    )
    def mutate(self, info, input):
        organization_id = input.get('id')

        if is_duplicate_name(organization_id, input):
            raise ServiceException(ORG_EXISTS_MESSAGE)

        organization = update_organization_base_details(organization_id, input)
        update_csm_user(organization, input)
        update_ca_user(organization, input)

        if contract_sign_date in input.keys():
            organization.contract_sign_date = input.get('contract_sign_date')
            organization.save()

        file_name = input.get('file_name')
        file_contents = input.get('file_contents')

        if file_name is not None and file_contents is not None:
            organization.logo = File(
                name=file_name,
                file=(
                    io.BytesIO(base64.b64decode(file_contents) if file_contents else "")
                ),
            )
            organization.save()

        logger.info(f'Organization {organization.name} successfully edited')

        logger.info(
            f'Organization with SFDC ID: {organization.sfdc_id} and is internal'
            f' {organization.is_internal}'
        )
        if organization.sfdc_id and not organization.is_internal:
            logger.info('Should send request to salesforce')
            # update_organization_in_salesforce(str(organization.id))

        return UpdateOrganizationById(data=organization)


class UpdateOnboardingStepCompletion(graphene.Mutation):
    class Arguments:
        input = OnboardingStepCompletionInput(required=True)

    step = graphene.Field(SetupStepType)

    @concierge_service(
        permission='user.change_concierge',
        exception_msg='Failed to toggle onboarding step completion status',
        revision_name='Can update onboarding step completion status',
    )
    def mutate(self, info, input):
        try:
            with transaction.atomic():
                step = OnboardingSetupStep.objects.filter(
                    name=input.get('name'),
                    onboarding__organization_id=input.get('organization_id'),
                ).first()

                if step:
                    step.completed = input.get('completed')
                    step.save()

                return UpdateOnboardingStepCompletion(step)
        except Exception as e:
            logger.exception(f'Error trying to update onboarding step completion: {e}')

            return ServiceException(errors.UPDATE_ORG_ONBOARDING_STEP_COMPLETION_ERROR)


class MoveOrgOutOfOnboarding(graphene.Mutation):
    class Arguments:
        input = MoveOrgOutOfOnboardingInput(required=True)

    success = graphene.Boolean()

    @concierge_service(
        permission='user.change_concierge',
        exception_msg='Failed to move organization out of onboarding',
        revision_name='Can move organization out of onboarding',
    )
    def mutate(self, info, input: MoveOrgOutOfOnboardingInput):
        try:
            with transaction.atomic():
                steps = (
                    Organization.objects.get(id=input.organization_id)
                    .onboarding.get()
                    .setup_steps.all()
                )

                for step in steps:
                    step.completed = True
                    step.save()

                return MoveOrgOutOfOnboarding(success=True)
        except Exception as e:
            logger.exception(
                f'Error trying to move organization out of onboarding: {e}'
            )

            return ServiceException(errors.CANNOT_MOVE_ORG_OUT_OF_ONBOARDING)


class CreateOrganizationCheckIn(graphene.Mutation):
    class Arguments:
        input = CreateOrganizationCheckInInput(required=True)

    success = graphene.Boolean()
    error = graphene.Field(ErrorType)

    @concierge_service(
        permission='user.add_concierge',
        exception_msg='Failed to create checkin',
        revision_name='Can add concierge',
    )
    def mutate(self, info, input):
        success = True
        error = None
        try:
            with transaction.atomic():
                organization_id = input.get('id')
                organization = Organization.objects.get(id=organization_id)
                username = input.get('cx_id')
                user = User.objects.get(username=username)

                CheckIn.objects.create(
                    organization=organization,
                    cx_participant=user,
                    date=input.get('date'),
                    customer_participant=input.get('customer_participant'),
                    notes=input.get('notes'),
                    action_items=input.get('action_items'),
                )

                return CreateOrganizationCheckIn(success=success, error=error)
        except Exception:
            logger.exception(errors.CANNOT_CREATE_ORGANIZATION_CHECK_IN)
            custom_error = errors.CREATE_ORG_CHECKIN_ERROR
            error = error if error is not None else custom_error

            return CreateOrganizationCheckIn(success=False, error=error)


class DeleteOrganizationCheckIn(graphene.Mutation):
    class Arguments:
        input = DeleteOrganizationCheckInInput(required=True)

    success = graphene.Boolean()
    error = graphene.Field(ErrorType)

    @concierge_service(
        permission='user.remove_concierge',
        exception_msg='Failed to remove checkin',
        revision_name='Can remove concierge',
    )
    def mutate(self, info, input):
        success = True
        error = None
        try:
            with transaction.atomic():
                check_in_ids = input.get('check_in_ids')

                for check_in_id in check_in_ids:
                    check_in = CheckIn.objects.get(id=check_in_id)
                    check_in.active = False
                    check_in.save()

                return CreateOrganizationCheckIn(success=success, error=error)
        except Exception:
            logger.exception(errors.CANNOT_DELETE_ORGANIZATION_CHECK_IN)
            custom_error = errors.DELETE_ORG_CHECKIN_ERROR
            error = error if error is not None else custom_error

            return CreateOrganizationCheckIn(success=False, error=error)


class DeleteCheckListStep(graphene.Mutation):
    class Arguments:
        checklist_id = graphene.Int(required=True)
        input = graphene.List(graphene.Int, required=True)

    success = graphene.Boolean(default_value=False)

    @laika_service(
        permission='organization.change_organizationchecklist',
        exception_msg='Failed to delete checklist step. Please try again',
        revision_name='Delete checklist step',
    )
    def mutate(self, info, **kwargs):
        checklist_id = kwargs['checklist_id']
        ids_to_delete = kwargs['input']
        organization = info.context.user.organization

        checklist = OrganizationChecklist.objects.get(
            id=checklist_id, organization=organization
        )

        checklist.action_item.steps.filter(
            Q(
                (Q(metadata__isTemplate__isnull=True) | Q(metadata__isTemplate=False))
                & Q(id__in=ids_to_delete)
            )
        ).delete()

        return DeleteCheckListStep(success=True)


class UpdateCheckListStep(graphene.Mutation):
    class Arguments:
        id = graphene.Int()
        name = graphene.String(required=False)
        description = graphene.String(required=True)
        parent_action_item = graphene.Int()
        metadata = graphene.JSONString()

    check_list_step = graphene.Field(CheckListStepType)

    @laika_service(
        permission='organization.change_organizationchecklist',
        exception_msg='Failed to add or update checklist step',
        revision_name='Add or Update checklist step',
    )
    def mutate(self, info, **kwargs):
        parent_action_item = ActionItem.objects.get(
            id=kwargs.get('parent_action_item'),
            checklist__organization=info.context.user.organization,
        )
        obj, _ = ActionItem.objects.update_or_create(
            id=kwargs.get('id'),
            defaults={
                'name': (
                    f'{parent_action_item.name}, '
                    f'{info.context.user.organization.name}, step'
                ),
                'description': kwargs.get('description', ''),
                'parent_action_item': parent_action_item,
                'metadata': kwargs.get('metadata', {}),
            },
        )

        return UpdateCheckListStep(check_list_step=obj)


class CreateChecklistTag(graphene.Mutation):
    class Arguments:
        checklist_id = graphene.Int(required=True)
        name = graphene.String(required=True)
        step_id = graphene.Int(required=True)

    tag = graphene.Field(TagType)

    @laika_service(
        permission='organization.change_organizationchecklist',
        exception_msg='Failed to add checklist tag',
        revision_name='Add checklist tag',
    )
    def mutate(self, info, **kwargs):
        organization = info.context.user.organization
        checklist = OrganizationChecklist.objects.get(
            id=kwargs.get('checklist_id'), organization=organization
        )
        step = ActionItem.objects.get(
            id=kwargs.get('step_id'), parent_action_item=checklist.action_item
        )

        try:
            tag = Tag.objects.get(
                name__exact=kwargs.get('name'),
                organization=organization,
            )
        except Tag.DoesNotExist:
            tag = Tag.objects.create(
                name=kwargs.get('name'),
                organization=organization,
            )
        checklist.tags.add(tag)
        step.metadata['category'] = {'id': tag.id, 'name': tag.name}
        step.save()

        return CreateChecklistTag(tag=tag)


class UseTemplateChecklist(graphene.Mutation):
    class Arguments:
        checklist_id = graphene.Int(required=True)

    checklist = graphene.List(ActionItemTypeV2)

    @laika_service(
        permission='organization.change_organizationchecklist',
        exception_msg='Failed to use template checklist step',
        revision_name='Add or Update checklist step',
    )
    def mutate(self, info, **kwargs):
        checklist = OrganizationChecklist.objects.get(id=kwargs.get('checklist_id'))
        objects_to_clone, ids_to_delete = [], []
        for item in checklist.action_item.steps.all().order_by('id'):
            if item.metadata.get('isTemplate') is True:
                item.id = None
                item.metadata['isTemplate'] = False
                objects_to_clone.append(item)
            else:
                ids_to_delete.append(item.id)
        ActionItem.objects.filter(id__in=ids_to_delete).delete()
        new_actions = ActionItem.objects.bulk_create(objects_to_clone)

        return UseTemplateChecklist(checklist=new_actions)


class CreateChecklistRun(graphene.Mutation):
    class Arguments:
        user_id = graphene.String(required=True)
        checklist_name = graphene.String(required=True)

    checklist_run = graphene.Field(OrganizationChecklistRunType)

    @laika_service(
        permission='organization.add_organizationchecklistrun',
        exception_msg='Failed to create checklist run',
        revision_name='Create checklist run',
    )
    def mutate(self, info, **kwargs):
        owner = find_user_by_id_type(kwargs.get('user_id'), info)
        checklist = OrganizationChecklist.objects.get(
            action_item__name=kwargs.get('checklist_name'),
            organization=info.context.user.organization,
        )
        checklist_run, _ = OrganizationChecklistRun.objects.get_or_create(
            owner=owner,
            checklist=checklist,
            defaults={'date': owner.end_date or datetime.today()},
        )

        return CreateChecklistRun(checklist_run=checklist_run)


class UpdateChecklistRun(graphene.Mutation):
    class Arguments:
        checklist_run_id = graphene.Int(required=True)
        date = graphene.Date(required=True)
        metadata = graphene.String(required=True)

    checklist_run = graphene.Field(OrganizationChecklistRunType)

    @laika_service(
        permission='organization.change_organizationchecklistrun',
        exception_msg='Failed to update checklist run',
        revision_name='Create checklist run',
    )
    def mutate(self, info, **kwargs):
        checklist_run_id = kwargs.get('checklist_run_id')

        obj, _ = OrganizationChecklistRun.objects.update_or_create(
            id=checklist_run_id,
            defaults={
                'date': kwargs.get('date'),
                'metadata': json.loads(kwargs.get('metadata')),
            },
        )

        return UpdateChecklistRun(checklist_run=obj)


class UpdateChecklistRunResource(graphene.Mutation):
    class Arguments:
        ids = graphene.List(graphene.Int)
        date = graphene.Date(required=False)
        status = graphene.String(required=False)
        resource_type = graphene.String(required=True)
        checklist_run = graphene.Int(required=True)

    checklist_resources = graphene.List(OrganizationChecklistRunResourceType)

    @classmethod
    def single_creation(cls, fields, model, checklist_run, resource):
        new_obj, _ = model.objects.update_or_create(
            checklist_run=checklist_run, **resource, defaults=fields
        )
        return new_obj

    @classmethod
    def get_fields_to_update(cls, **kwargs):
        status = kwargs.get('status')
        date = kwargs.get('date')
        fields = {}
        if status and status in OffboardingStatus.values:
            new_date = datetime.now() if status == OffboardingStatus.COMPLETED else None
            fields.update({'status': status, 'date': new_date})
        if date:
            fields.update({'date': date})

        return fields

    @laika_service(
        permission='organization.change_organizationchecklist',
        exception_msg='Failed to update checklist run step',
        revision_name='Add or Update checklist run step',
    )
    def mutate(self, info, **kwargs):
        resource_type = kwargs.get('resource_type')
        if resource_type == 'vendor':
            model = OffboardingVendor
            related_field = 'vendor_id'
        elif resource_type == 'step':
            model = OrganizationChecklistRunSteps
            related_field = 'action_item_id'
        else:
            raise ServiceException('The resource name is invalid')

        ids = kwargs.get('ids')
        checklist_run_id = kwargs.get('checklist_run')
        organization = info.context.user.organization
        checklist_run = OrganizationChecklistRun.objects.get(
            id=checklist_run_id, checklist__organization_id=organization.id
        )
        fields = UpdateChecklistRunResource.get_fields_to_update(**kwargs)
        objects_updated = [
            UpdateChecklistRunResource.single_creation(
                fields, model, checklist_run, {related_field: _id}
            )
            for _id in ids
        ]

        return UpdateChecklistRunResource(checklist_resources=objects_updated)


class DeleteApiToken(graphene.Mutation):
    api_token_id = graphene.Int()

    class Arguments:
        id = graphene.Int(required=True)

    @laika_service(
        permission='organization.delete_apitokenhistory',
        exception_msg='Failed to delete Organization API Token',
        revision_name='API Token deleted',
    )
    def mutate(self, info, id):
        user = info.context.user
        api_token = ApiTokenHistory.objects.get(
            id=id, organization=info.context.user.organization
        )
        with reversion.create_revision():
            reversion.set_user(info.context.user)
            reversion.set_comment(f'API Token deleted: {api_token.name}')
            api_token.delete()
        user_info = f'API Token deleted by: {user.username} '
        organization_info = f'organization: {user.organization.id}'
        logger.info(user_info + organization_info)
        return DeleteApiToken(api_token_id=id)


class CreateApiToken(graphene.Mutation):
    id = graphene.Int()
    token = graphene.String()

    class Arguments:
        name = graphene.String(required=True)

    @laika_service(
        permission='organization.add_apitokenhistory',
        exception_msg='Failed to create Organization API Token',
        revision_name='API Token created',
    )
    def mutate(self, info, name):
        user = info.context.user
        api_token, api_token_record = generate_api_token(user=user, name=name)
        with reversion.create_revision():
            reversion.set_user(info.context.user)
            reversion.set_comment(
                f'API Token created by : {user.first_name} {user.last_name} '
                f'organization: {user.organization.id}'
            )
        user_info = f'API Token created by: {user.username} '
        organization_info = f'organization: {user.organization.id}'
        logger.info(user_info + organization_info)

        return CreateApiToken(token=api_token, id=api_token_record.id)


class SubmitOnboardingV2Form(graphene.Mutation):
    success = graphene.Boolean()
    error = graphene.Field(ErrorType)

    class Arguments:
        response_id = graphene.String()

    @laika_service(
        permission='organization.change_organization',
        exception_msg='Failed to submit onboarding form',
        revision_name='Submit onboarding form',
    )
    def mutate(self, info, response_id: str):
        user = info.context.user
        organization = info.context.user.organization
        questionary_response = get_typeform_answer_from_response(
            ONBOARDING_TYPEFORM_FORM, response_id
        )
        if not questionary_response:
            return SubmitOnboardingV2Form(
                success=False, error='Questionary response was not found'
            )

        OnboardingResponse.objects.create(
            organization=organization,
            submitted_by_id=user.id,
            questionary_response=questionary_response,
            response_id=response_id,
            questionary_id=ONBOARDING_TYPEFORM_FORM,
        )

        process_organization_vendors.delay(questionary_response, organization.id)
        pool.apply_async(
            process_invite_onboarding_users,
            args=(questionary_response, organization, user),
        )

        formula = f'{"{Organization ID}"} = "{organization.id}"'
        tddq_execution.delay(formula)

        return SubmitOnboardingV2Form(success=True, error=None)


# Complete onboarding for Onboarding V2
class CompleteOnboarding(graphene.Mutation):
    success = graphene.Boolean()
    error = graphene.Field(ErrorType)

    @laika_service(
        permission='organization.change_organization',
        exception_msg='Failed to complete onboarding',
        revision_name='Organization onboarding',
    )
    def mutate(self, info, **kwargs):
        organization = info.context.user.organization
        organization.state = ACTIVE_STATE
        organization.save()

        onboarding = organization.onboarding.first()
        onboarding.state = COMPLETED_STATE
        onboarding.save()
        return CompleteOnboarding(success=True, error=None)


# Update onboarding v2 state step
class UpdateOnboardingV2State(graphene.Mutation):
    success = graphene.Boolean()
    error = graphene.Field(ErrorType)

    class Arguments:
        state_v2 = graphene.String()

    @laika_service(
        permission='organization.change_organization',
        exception_msg='Failed to update onboarding state',
        revision_name='Update organization onboarding state',
    )
    def mutate(self, info, state_v2: str):
        organization = info.context.user.organization
        onboarding = organization.onboarding.first()
        onboarding.state_v2 = state_v2
        onboarding.full_clean()
        onboarding.save()
        return UpdateOnboardingV2State(success=True, error=None)


# CA call onboarding V2
class BookOnboardingMeeting(graphene.Mutation):
    onboarding = graphene.Field(OnboardingResponseType)

    class Arguments:
        event_id = graphene.String(required=True)
        invitee_id = graphene.String(required=True)

    @laika_service(
        permission='organization.change_onboarding',
        exception_msg='Failed to book onboarding meeting',
        revision_name='Book onboarding meeting',
    )
    def mutate(self, info, **kwargs):
        calendly_event_id = kwargs['event_id']
        calendly_invitee_id = kwargs['invitee_id']

        organization = info.context.user.organization
        onboarding = organization.onboarding.first()
        onboarding.calendly_event_id_v2 = calendly_event_id
        onboarding.calendly_invitee_id_v2 = calendly_invitee_id
        onboarding.save()

        return BookOnboardingMeeting(onboarding=onboarding)


class ValidateOnboardingMeeting(graphene.Mutation):
    onboarding = graphene.Field(OnboardingResponseType)

    @laika_service(
        permission='organization.change_onboarding',
        exception_msg='Failed to validate onboarding meeting',
        revision_name='Validate onboarding meeting',
    )
    def mutate(self, info, **kwargs):
        organization = info.context.user.organization
        onboarding = organization.onboarding.first()
        if onboarding.calendly_event_id_v2:
            validate_event(onboarding)

        return BookOnboardingMeeting(onboarding=onboarding)

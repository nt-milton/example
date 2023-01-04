import logging

import graphene
from django.db.models import F, Q
from django.db.models.query import Prefetch

import organization.errors as errors
from certification.models import UnlockedOrganizationCertification
from control.models import Control, RoadMap
from laika.auth import login_required
from laika.decorators import concierge_service, laika_service
from laika.types import OrderInputType, PaginationInputType
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.exceptions import service_exception
from laika.utils.paginator import get_paginated_result
from laika.utils.permissions import map_permissions
from organization.calendly.rest_client import validate_event
from seeder.constants import ALL_MY_COMPLIANCE_ORGS

from .constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from .filters import get_filter_query, roadmap_filter_query
from .inputs import (
    OrganizationCheckInFilterType,
    OrganizationFilterType,
    RoadmapFilterInputType,
)
from .models import (
    ApiTokenHistory,
    Onboarding,
    Organization,
    OrganizationChecklist,
    OrganizationLocation,
)
from .mutations import (
    BookOnboardingMeeting,
    CompleteOnboarding,
    CreateApiToken,
    CreateChecklistRun,
    CreateChecklistTag,
    CreateLocation,
    CreateOrganization,
    CreateOrganizationCheckIn,
    DeleteApiToken,
    DeleteCheckListStep,
    DeleteLocation,
    DeleteOrganizationCheckIn,
    InviteAndCompleteOnboarding,
    MoveOrgOutOfOnboarding,
    SubmitOnboardingV2Form,
    UpdateChecklistRun,
    UpdateChecklistRunResource,
    UpdateCheckListStep,
    UpdateLocation,
    UpdateOnboarding,
    UpdateOnboardingStepCompletion,
    UpdateOnboardingV2State,
    UpdateOrganization,
    UpdateOrganizationById,
    UseTemplateChecklist,
    ValidateOnboardingMeeting,
)
from .offboarding.mutations import RunAccessScan
from .onboarding.onboarding_content import get_onboarding_form_text_answer
from .salesforce.mutations import SyncSalesforceData
from .types import (
    ApiTokenHistoryType,
    CheckInResponseType,
    LocationResponseType,
    OnboardingExpertType,
    OnboardingResponseType,
    OrganizationChecklistType,
    OrganizationResponseType,
    OrganizationsResponseType,
    RoadmapType,
)

logger = logging.getLogger('Organization')
CSM = 'customer_success_manager_user'
CA = 'compliance_architect_user'

TYPE_FORM_TECHNICAL_CONTACT_EMAIL = 'primary_technical_contact_email_address'
TYPE_FORM_TECHNICAL_CONTACT_NAME = 'primary_technical_contact_first_name'
TYPE_FORM_TECHNICAL_CONTACT_LAST_NAME = 'primary_technical_contact_last_name'


def get_filtered_organizations(organizations, filter_by):
    filter_query = get_filter_query(filter_by)
    return organizations.filter(filter_query)


def get_sorted_organizations(organizations, **kwargs):
    order_by = kwargs.get('order_by', {'field': 'created_at', 'order': 'descend'})

    field = order_by.get('field')
    if field == CA or field == CSM:
        order_query = (
            '-' + f'{field}__first_name'
            if order_by.get('order') == 'descend'
            else f'{field}__first_name'
        )

        return organizations.order_by(order_query)

    order_query = '-' + field if order_by.get('order') == 'descend' else field

    return organizations.order_by(order_query)


class Query(object):
    get_organization_by_id = graphene.Field(
        OrganizationResponseType, id=graphene.String(required=True)
    )
    get_organization = graphene.Field(OrganizationResponseType)
    get_organization_summary = graphene.Field(
        OrganizationResponseType, id=graphene.String()
    )
    onboarding = graphene.Field(OnboardingResponseType)
    onboarding_by_organization = graphene.Field(
        OnboardingResponseType,
        organization_id=graphene.UUID(required=True),
    )
    locations = graphene.List(LocationResponseType)
    get_all_organizations = graphene.Field(
        OrganizationsResponseType,
        order_by=graphene.Argument(OrderInputType, required=False),
        own=graphene.Boolean(),
        pagination=graphene.Argument(PaginationInputType, required=False),
        filter=graphene.List(OrganizationFilterType, required=False),
        search_criteria=graphene.String(required=False),
    )
    check_ins = graphene.Field(
        CheckInResponseType,
        id=graphene.UUID(required=True),
        order_by=graphene.Argument(OrderInputType, required=False),
        pagination=graphene.Argument(PaginationInputType, required=False),
        filter=graphene.List(OrganizationCheckInFilterType, required=False),
        search_criteria=graphene.String(required=False),
    )
    roadmap = graphene.Field(
        RoadmapType,
        filters=graphene.Argument(RoadmapFilterInputType),
    )

    offboarding = graphene.Field(OrganizationChecklistType)

    checklist = graphene.Field(
        OrganizationChecklistType, name=graphene.String(required=True)
    )
    api_tokens = graphene.List(ApiTokenHistoryType)

    get_onboarding_expert = graphene.Field(OnboardingExpertType)

    @concierge_service(
        permission='user.view_concierge',
        exception_msg='Failed to get organization',
        revision_name='Can view concierge',
    )
    def resolve_get_organization_by_id(self, info, id):
        try:
            organization = Organization.objects.get(id=id)
            current_user = info.context.user
            permissions = map_permissions(current_user, 'organization')

            return OrganizationResponseType(
                data=organization,
                permissions=permissions,
            )

        except Exception:
            logger.exception(errors.CANNOT_GET_ORGANIZATION_BY_ID)
            return OrganizationResponseType(
                error=errors.GET_ORG_ERROR, success=False, data=None
            )

    @concierge_service(
        permission='user.view_concierge',
        exception_msg='Failed to get organization check ins',
        revision_name='Can view concierge',
    )
    def resolve_check_ins(self, info, **kwargs):
        order_by = kwargs.get('order_by', {'field': 'date', 'order': 'descend'})
        field = order_by.get('field')
        order = order_by.get('order')
        order_query = (
            F(field).desc(nulls_last=True)
            if order == 'descend'
            else F(field).asc(nulls_last=True)
        )

        search_criteria = kwargs.get('search_criteria', '')
        filter_by = kwargs.get('filter', {})
        filter_query = get_filter_query(filter_by)
        check_ins = (
            Organization.objects.get(id=kwargs.get('id'))
            .check_ins.filter(Q(active=True) & (filter_query))
            .order_by(order_query)
        )
        filtered_check_ins = check_ins.filter(filter_query).filter(
            Q(cx_participant__first_name__icontains=search_criteria)
            | Q(customer_participant__icontains=search_criteria)
            | Q(notes__icontains=search_criteria)
            | Q(action_items__icontains=search_criteria)
        )
        pagination = kwargs.get('pagination')
        page = pagination.page if pagination else DEFAULT_PAGE
        page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE
        paginated_result = get_paginated_result(filtered_check_ins, page_size, page)

        return CheckInResponseType(
            data=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @concierge_service(
        permission='user.view_concierge',
        exception_msg='''
        Failed to retrieve organization list. Permission denied.''',
        revision_name='Can view concierge',
    )
    @service_exception('Failed to retrieve organizations')
    def resolve_get_all_organizations(self, info, **kwargs):
        current_user = info.context.user

        filter_by = kwargs.get('filter', {})
        search_criteria = kwargs.get('search_criteria', '')

        all_organizations = Organization.objects.filter(~Q(name=ALL_MY_COMPLIANCE_ORGS))

        if kwargs.get('own'):
            all_organizations = all_organizations.filter(
                Q(customer_success_manager_user=current_user.id)
                | Q(compliance_architect_user=current_user.id)
            )

        sorted_organizations = get_sorted_organizations(
            get_filtered_organizations(all_organizations, filter_by), **kwargs
        )

        if search_criteria:
            sc = search_criteria
            sorted_organizations = sorted_organizations.filter(
                Q(name__icontains=search_criteria)
                | Q(customer_success_manager_user__first_name__icontains=sc)
                | Q(compliance_architect_user__first_name__icontains=sc)
            )

        pagination = kwargs.get('pagination')
        page = pagination.page if pagination else DEFAULT_PAGE
        page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE
        paginated_result = get_paginated_result(sorted_organizations, page_size, page)

        return OrganizationsResponseType(
            data=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @login_required
    def resolve_get_organization(self, info, **kwargs):
        try:
            current_user = info.context.user
            permissions = map_permissions(current_user, 'organization')

            data = info.context.user.organization

            return OrganizationResponseType(
                data=data,
                permissions=permissions,
            )

        except Exception:
            logger.exception(errors.CANNOT_GET_ORGANIZATION)
            return OrganizationResponseType(
                error=errors.GET_ORG_ERROR, success=False, data=None
            )

    @login_required
    def resolve_get_organization_summary(self, info, **kwargs):
        try:
            return OrganizationResponseType(data=info.context.user.organization)
        except Exception:
            logger.exception(errors.CANNOT_GET_ORGANIZATION_SUMMARY)
            return OrganizationResponseType(
                error=errors.GET_ORG_SUMMARY_ERROR, success=False, data=None
            )

    @laika_service(
        atomic=False,
        permission='organization.view_onboarding',
        exception_msg='Failed to get Onboarding',
    )
    def resolve_onboarding(self, info, **kwargs):
        organization = info.context.user.organization
        onboarding = Onboarding.objects.filter(organization=organization).first()
        if onboarding and onboarding.calendly_event_id_v2:
            validate_event(onboarding)
        return onboarding

    @concierge_service(
        permission='user.view_concierge',
        exception_msg='Failed to get onboarding list by organization id',
        revision_name='Can view concierge',
    )
    def resolve_onboarding_by_organization(self, info, **kwargs):
        organization_id = kwargs.get('organization_id')
        return Onboarding.objects.filter(organization_id=organization_id).first()

    @laika_service(
        permission='organization.view_organizationlocation',
        exception_msg='Failed to get locations',
    )
    def resolve_locations(self, info, **kwargs):
        organization = info.context.user.organization
        locations = []
        org_locations = (
            OrganizationLocation.objects.filter(organization=organization)
            .select_related('address')
            .order_by('id')
        )
        for org_location in org_locations:
            address = org_location.address
            locations.append(
                LocationResponseType(
                    id=address.id,
                    street1=address.street1,
                    street2=address.street2,
                    city=address.city,
                    country=address.country,
                    state=address.state,
                    zip_code=address.zip_code,
                    name=org_location.name,
                    hq=org_location.hq,
                )
            )
        return locations

    @laika_service(
        permission='organization.view_organizationchecklist',
        exception_msg='Failed to get Organization Checklist',
    )
    def resolve_offboarding(self, info, **kwargs):
        return OrganizationChecklist.objects.get(
            action_item__metadata__type='offboarding',
            organization=info.context.user.organization,
        )

    @laika_service(
        permission='organization.view_organizationchecklist',
        exception_msg='Failed to get Organization Checklist',
    )
    def resolve_checklist(self, info, **kwargs):
        checklist_name = kwargs.get('name')
        return OrganizationChecklist.objects.get(
            action_item__name=checklist_name,
            organization=info.context.user.organization,
        )

    @laika_service(
        permission='control.view_roadmap',
        exception_msg='Failed to get Organization roadmap',
    )
    def resolve_roadmap(self, info, **kwargs):
        organization = info.context.user.organization

        filter_query = roadmap_filter_query(kwargs.get('filters'))

        roadmap_qs = (
            RoadMap.objects.filter(organization=organization)
            .prefetch_related(
                'groups',
                Prefetch(
                    'groups__controls', queryset=Control.objects.filter(filter_query)
                ),
            )
            .first()
        )
        groups_qs = roadmap_qs.groups.all() if roadmap_qs else []
        backlog_qs = Control.objects.filter(
            filter_query, group=None, organization=organization
        )

        completion_date = None
        filter_by_framework_id = kwargs.get('filters', {}).get('framework', None)
        if filter_by_framework_id:
            completion_date = (
                UnlockedOrganizationCertification.objects.filter(
                    organization_id=organization.id,
                    certification_id=filter_by_framework_id,
                )
                .first()
                .target_audit_completion_date
            )

        return RoadmapType(
            completion_date=completion_date, groups=groups_qs, backlog=backlog_qs
        )

    @laika_service(
        permission='organization.view_apitokenhistory',
        exception_msg='Failed to get Organization API Tokens',
    )
    def resolve_api_tokens(self, info, **kwargs):
        organization = info.context.user.organization
        return ApiTokenHistory.objects.filter(organization=organization).all()

    @laika_service(
        permission='organization.change_onboarding',
        exception_msg='Failed to get onboarding expert',
    )
    def resolve_get_onboarding_expert(self, info, **kwargs):
        organization = info.context.user.organization

        contact_email_address = get_onboarding_form_text_answer(
            organization, TYPE_FORM_TECHNICAL_CONTACT_EMAIL
        )
        contact_first_name = get_onboarding_form_text_answer(
            organization, TYPE_FORM_TECHNICAL_CONTACT_NAME
        )
        contact_last_name = get_onboarding_form_text_answer(
            organization, TYPE_FORM_TECHNICAL_CONTACT_LAST_NAME
        )

        return OnboardingExpertType(
            firstName=contact_first_name,
            lastName=contact_last_name,
            email=contact_email_address,
        )


class Mutation(graphene.ObjectType):
    create_organization = CreateOrganization.Field()
    update_organization = UpdateOrganization.Field()
    update_organization_by_id = UpdateOrganizationById.Field()
    update_onboarding_step_completion = UpdateOnboardingStepCompletion.Field()
    update_onboarding = UpdateOnboarding.Field()
    invite_and_complete_onboarding = InviteAndCompleteOnboarding.Field()
    create_location = CreateLocation.Field()
    update_location = UpdateLocation.Field()
    delete_location = DeleteLocation.Field()
    create_checkin = CreateOrganizationCheckIn.Field()
    delete_checkin = DeleteOrganizationCheckIn.Field()
    delete_checklist_step = DeleteCheckListStep.Field()
    update_checklist_step = UpdateCheckListStep.Field()
    create_checklist_tag = CreateChecklistTag.Field()
    use_template_checklist = UseTemplateChecklist.Field()
    create_checklist_run = CreateChecklistRun.Field()
    update_checklist_run_resource = UpdateChecklistRunResource.Field()
    update_checklist_run = UpdateChecklistRun.Field()
    run_access_scan = RunAccessScan.Field()
    delete_api_token = DeleteApiToken.Field()
    create_api_token = CreateApiToken.Field()
    move_org_out_of_onboarding = MoveOrgOutOfOnboarding.Field()
    submit_onboarding_v2_form = SubmitOnboardingV2Form.Field()
    complete_onboarding = CompleteOnboarding.Field()
    update_onboarding_v2_state = UpdateOnboardingV2State.Field()
    book_onboarding_meeting = BookOnboardingMeeting.Field()
    validate_onboarding_meeting = ValidateOnboardingMeeting.Field()
    sync_salesforce_data = SyncSalesforceData.Field()

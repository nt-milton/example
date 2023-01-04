import base64
import io
import logging
import time

import graphene
import requests
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.files import File
from django.db import transaction
from django.db.models import Q

import policy.errors as errors
from control.models import ControlPillar
from control.types import ControlPillarType
from feature.constants import new_controls_feature_flag, playbooks_feature_flag
from laika import settings
from laika.auth import login_required, permission_required
from laika.decorators import laika_service
from laika.types import (
    BaseResponseType,
    ErrorType,
    FileType,
    FiltersType,
    InputFileType,
    PaginationResponseType,
)
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.exceptions import ServiceException, service_exception
from laika.utils.files import filename_has_extension, get_docx_file_content
from laika.utils.history import create_revision
from laika.utils.order_by import get_default_order_by_query
from laika.utils.paginator import get_paginated_result
from laika.utils.permissions import map_permissions
from policy.docx_helper import get_validated_docx_file, remove_proposed_changes
from policy.models import Policy, PublishedPolicy, User
from policy.tasks import generate_policy_embeddings_task
from policy.types import PolicyType, PolicyTypes, PublishedPolicyType
from policy.utils.filter_builder import FilterBuilder
from policy.utils.utils import (
    are_policies_completed_by_user,
    create_or_delete_action_items_by_policy,
    create_policy_action_items_by_users,
    update_action_items_by_policy,
)
from tag.models import Tag
from user.helpers import get_user_by_email
from user.utils.compliant import is_user_compliant_completed

from .helpers import (
    get_policy_filters,
    get_publish_policy_error_message,
    validate_administrator_is_empty,
)
from .models import OnboardingPolicy
from .mutations import (
    ReplacePolicy,
    UpdateIsDraftEdited,
    UpdateNewPolicy,
    UpdateOnboardingPolicy,
)
from .types import FiltersPolicyType, OnboardingPolicyType

DEFAULT_PAGE_SIZE = 50

logger = logging.getLogger('policy')

ONLY_OFFICE_COMMAND_SERVICE_URL = (
    f'{settings.DOCUMENT_SERVER_URL}/coauthoring/CommandService.ashx'
)


class PolicyResponseType(BaseResponseType):
    data = graphene.Field(PolicyType)
    permissions = graphene.List(graphene.String)


class PoliciesResponseType(BaseResponseType):
    data = graphene.List(PolicyType)
    permissions = graphene.List(graphene.String)
    pagination = graphene.Field(PaginationResponseType)


class VersionHistoryResponseType(BaseResponseType):
    data = graphene.List(PublishedPolicyType)


class PublishedPolicyResponseType(BaseResponseType):
    data = graphene.Field(PublishedPolicyType)


class PolicyOrderInputType(graphene.InputObjectType):
    field = graphene.String(required=True)
    order = graphene.String(required=True)


class Query(object):
    policy = graphene.Field(PolicyResponseType, id=graphene.UUID())
    policies = graphene.Field(
        PoliciesResponseType,
        order_by=graphene.Argument(PolicyOrderInputType, required=False),
        ids=graphene.List(graphene.UUID),
    )
    published_policies = graphene.Field(
        PoliciesResponseType, dataroom_only=graphene.Boolean()
    )
    version_history = graphene.Field(VersionHistoryResponseType, id=graphene.UUID())
    version_preview = graphene.Field(
        PublishedPolicyResponseType,
        policy_id=graphene.UUID(),
        version_id=graphene.Int(),
    )
    onboarding_policies = graphene.List(OnboardingPolicyType)
    filtered_policies = graphene.Field(
        PoliciesResponseType,
        page_size=graphene.Int(),
        page=graphene.Int(),
        filters=graphene.Argument(FiltersPolicyType, required=False),
        order_by=graphene.Argument(PolicyOrderInputType, required=False),
    )
    control_families = graphene.List(ControlPillarType)
    policy_filters = graphene.List(FiltersType)

    @login_required
    def resolve_control_families(self, info, **kwargs):
        return ControlPillar.objects.all()

    @login_required
    def resolve_policy(self, info, **kwargs):
        policy_id = kwargs.get('id')
        try:
            policy = Policy.objects.get(
                pk=policy_id, organization=info.context.user.organization
            )
            return PolicyResponseType(
                data=policy, permissions=map_permissions(info.context.user, 'policy')
            )
        except Policy.DoesNotExist:
            logger.exception(f'Policy with ID {policy_id} does not exist')
            error = errors.CANNOT_GET_POLICY_ERROR
        except Exception:
            logger.exception(errors.MSG_CANNOT_GET_POLICY)
            error = errors.CANNOT_GET_POLICY_ERROR
        return PolicyResponseType(error=error, success=False, data=None)

    @login_required
    def resolve_policies(self, info, **kwargs):
        try:
            ids = kwargs.get('ids')
            order_by = kwargs.get('order_by', '')
            search_filter = {'id__in': ids} if ids else {}
            permission_filter = (
                {}
                if info.context.user.has_perm('policy.change_policy')
                else {'is_published': True}
            )
            return PoliciesResponseType(
                data=Policy.objects.filter(
                    organization=info.context.user.organization,
                    **permission_filter,
                    **search_filter,
                ).order_by(get_policies_sort(order_by)),
                permissions=map_permissions(info.context.user, 'policy'),
            )
        except Exception:
            logger.exception(errors.MSG_CANNOT_GET_POLICIES)
            error = errors.CANNOT_GET_POLICIES_ERROR
            return PoliciesResponseType(error=error, success=False, data=None)

    @login_required
    @service_exception('Cannot get published policies')
    def resolve_published_policies(self, info, **kwargs):
        policies = Policy.objects.filter(
            organization=info.context.user.organization, is_published=True
        )
        if kwargs.get('dataroom_only'):
            policies = policies.filter(is_visible_in_dataroom=True)
        return PoliciesResponseType(
            data=policies, permissions=map_permissions(info.context.user, 'policy')
        )

    @login_required
    def resolve_version_history(self, info, **kwargs):
        policy_id = kwargs.get('id')
        try:
            policy = Policy.objects.get(pk=policy_id)
            data = policy.versions.filter(version__gte=1).order_by('-version')
            return VersionHistoryResponseType(data=data)
        except Policy.DoesNotExist:
            logger.exception(f'Policy with ID {policy_id} does not exist')
            error = errors.CANNOT_GET_VERSION_HISTORY_ERROR
        except Exception:
            logger.exception(errors.MSG_CANNOT_GET_POLICY_VERSION_HISTORY)
            error = errors.CANNOT_GET_VERSION_HISTORY_ERROR
        return PolicyResponseType(error=error, success=False, data=None)

    @login_required
    def resolve_version_preview(self, info, **kwargs):
        policy_id = kwargs.get('policy_id')
        version_id = kwargs.get('version_id')
        try:
            published_policy = PublishedPolicy.objects.get(
                policy__id=policy_id,
                policy__organization=info.context.user.organization,
                version=version_id,
            )
            return PublishedPolicyResponseType(data=published_policy)
        except PublishedPolicy.DoesNotExist:
            logger.exception(
                f'Published Policy with ID {policy_id} and version '
                f'{version_id} does not exist'
            )
            error = errors.CANNOT_GET_VERSION_PREVIEW_ERROR
        except Exception:
            logger.exception(errors.CANNOT_GET_VERSION_PREVIEW_ERROR)
            error = errors.CANNOT_GET_VERSION_PREVIEW_ERROR
        return PublishedPolicyResponseType(error=error, success=False, data=None)

    @laika_service(
        permission='organization.view_onboarding',
        exception_msg='Failed to get onbaording policies',
    )
    def resolve_onboarding_policies(self, info, **kwargs):
        organization = info.context.user.organization
        return (
            OnboardingPolicy.objects.filter(organization=organization)
            .all()
            .order_by('id')
        )

    @login_required
    @service_exception('Cannot get filtered policies')
    def resolve_filtered_policies(self, info, **kwargs):
        order_query = get_default_order_by_query('display_id', **kwargs)
        filters = kwargs.get('filters', {})
        search = filters.get('search', '')
        search_filter = Q(name__unaccent__icontains=search)
        policy_filters = get_policy_filters(filters)
        data = info.context.user.organization.policies.filter(
            search_filter & policy_filters
        ).order_by(order_query)
        page = kwargs.get('page')
        page_size = kwargs.get('page_size') or DEFAULT_PAGE_SIZE
        paginated_result = get_paginated_result(data, page_size, page)
        return PoliciesResponseType(
            data=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @login_required
    def resolve_policy_filters(self, info, **kwargs):
        organization = info.context.user.organization
        # TODO: Remove this validation when all users
        # are migrated to My Compliance
        display_control_family_filter_name = organization.is_flag_active(
            new_controls_feature_flag
        ) and not organization.is_flag_active(playbooks_feature_flag)
        builder = FilterBuilder()
        builder.add_owners(organization.id)
        builder.add_type(organization.id)
        builder.add_category(organization.id, display_control_family_filter_name)
        builder.add_status(organization.id)
        builder.add_tags(organization.id, organization)
        filters = builder.export()
        return filters


class CreatePolicyInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    administrator_email = graphene.String()
    approver_email = graphene.String()
    owner_email = graphene.String()
    category = graphene.String(required=True)
    description = graphene.String(required=True)
    draft = graphene.InputField(InputFileType)
    tags = graphene.List(graphene.String, required=False)
    is_required = graphene.Boolean()
    control_family_id = graphene.Int()
    policy_type = graphene.String()


class CreatePolicyResponseType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    is_published = graphene.Boolean()
    policy_type = graphene.String()


class CreatePolicy(graphene.Mutation):
    class Arguments:
        input = CreatePolicyInput(required=True)

    success = graphene.Boolean()
    error = graphene.Field(ErrorType)
    data = graphene.Field(CreatePolicyResponseType)
    permissions = graphene.List(graphene.String)

    @staticmethod
    @login_required
    @permission_required('policy.add_policy')
    @create_revision('Created Policy')
    @transaction.atomic
    def mutate(root, info, input=None):
        data = None
        success = True
        error = None
        permissions = None
        user_email = None

        try:
            permissions = map_permissions(info.context.user, 'policy')
            doc = None
            if input.draft is not None:
                if 'draft' in info.context.FILES:
                    doc = info.context.FILES['draft']
                else:
                    doc = File(
                        name=input.draft.file_name,
                        file=io.BytesIO(base64.b64decode(input.draft.file)),
                    )
            else:
                empty_file = open('policy/assets/empty.docx', 'rb')
                doc = File(name=f'{input.name}.docx', file=empty_file)

            if not filename_has_extension(doc.name):
                raise ServiceException('Policy must be a docx file')

            organization_id = info.context.user.organization_id

            administrator = get_user_by_email(
                organization_id=organization_id, email=input.get('administrator_email')
            )
            approver = get_user_by_email(
                organization_id=organization_id, email=input.get('approver_email')
            )
            owner = get_user_by_email(
                organization_id=organization_id, email=input.get('owner_email')
            )

            control_family = None
            control_family_id = input.get('control_family_id')
            if control_family_id:
                control_family = ControlPillar.objects.get(id=control_family_id)

            policy_type = (
                PolicyTypes.PROCEDURE.value
                if PolicyTypes.PROCEDURE.value == input.get('policy_type')
                else PolicyTypes.POLICY.value
            )

            created_policy = Policy.objects.create(
                organization=info.context.user.organization,
                name=input.name,
                category=input.category,
                description=input.description,
                administrator=administrator,
                approver=approver,
                owner=owner,
                draft=doc,
                is_required=input.is_required,
                control_family=control_family,
                policy_type=policy_type,
            )
            if input.tags:
                for tag in input.tags:
                    created_tag, _ = Tag.objects.get_or_create(
                        name=tag, organization=info.context.user.organization
                    )
                    created_policy.tags.add(created_tag)

            data = CreatePolicyResponseType(
                id=created_policy.id,
                name=created_policy.name,
                is_published=created_policy.is_published,
                policy_type=policy_type,
            )
            error = ErrorType(code=None, message='')
            success = True
        except User.DoesNotExist:
            logger.exception(f'User with email {user_email} does not exist')
            data = None
            error = errors.DOES_NOT_EXIST_ERROR
            success = False
        except ValidationError:
            data = None
            error = errors.VALIDATION_ERROR
            success = False
        except Exception:
            policy_name = input.name
            logger.exception(f'Error to create policy with name {policy_name}')
            data = None
            error = errors.CANNOT_CREATE_POLICY_ERROR
            success = False

        return CreatePolicy(
            success=success, error=error, data=data, permissions=permissions
        )


class SavePolicyDocumentInput(graphene.InputObjectType):
    policy_id = graphene.UUID(required=True)


class SavePolicyDocumentResponseType(graphene.ObjectType):
    id = graphene.String()
    ok = graphene.Boolean()
    document_status = graphene.String()


class SavePolicyDocument(graphene.Mutation):
    class Arguments:
        input = SavePolicyDocumentInput(required=True)

    success = graphene.Boolean()
    error = graphene.Field(ErrorType)
    data = graphene.Field(SavePolicyDocumentResponseType)

    @staticmethod
    @login_required
    @permission_required('policy.publish_policy')
    def mutate(root, info, input=None):
        data = None
        success = True
        error = None

        try:
            policy = Policy.objects.get(
                id=input.policy_id, organization=info.context.user.organization
            )
            response = requests.post(
                ONLY_OFFICE_COMMAND_SERVICE_URL,
                headers={"Content-Type": "application/json"},
                json={"c": "forcesave", "key": policy.draft_key},
            )
            # This call to the sleep function is required here to give the time
            # to the document-server to ends with the forcesave
            time.sleep(7)
            document_server_errors = {
                0: "document_changed",
                3: "server_error",
                4: "no_changes_applied",
            }
            document_server_error = response.json()['error']
            data = SavePolicyDocumentResponseType(
                id=policy.id,
                ok=document_server_error == 0 or document_server_error == 4,
                document_status=document_server_errors.get(document_server_error),
            )
            error = ErrorType(code=None, message='')
            success = True
        except ObjectDoesNotExist:
            data = None
            error = errors.DOES_NOT_EXIST_ERROR
            success = False
        except ValidationError:
            data = None
            error = errors.VALIDATION_ERROR
            success = False
        except Exception:
            logger.exception(
                f'Error to save document for policy with ID {input.policy_id}'
            )
            data = None
            error = errors.CANNOT_SAVE_POLICY_DOCUMENT_ERROR
            success = False

        return SavePolicyDocument(success=success, error=error, data=data)


class PublishPolicyInput(graphene.InputObjectType):
    policy_id = graphene.String(required=True)
    comment = graphene.String(required=True)


class PublishPolicyResponseType(graphene.ObjectType):
    id = graphene.String()
    is_published = graphene.Boolean()
    published_at = graphene.String()
    version = graphene.String()
    draft = graphene.Field(FileType)


class PublishPolicy(graphene.Mutation):
    class Arguments:
        input = PublishPolicyInput(required=True)

    success = graphene.Boolean()
    error = graphene.Field(ErrorType)
    data = graphene.Field(PublishPolicyResponseType)

    @staticmethod
    @login_required
    @permission_required('policy.publish_policy')
    @create_revision('Published policy')
    def mutate(root, info, input=None):
        data = None
        success = True
        error = None

        # TODO - remove ff when all customers are migrated
        # to the new policy details view (revamp version)
        new_controls_ff_exists = info.context.user.organization.is_flag_active(
            new_controls_feature_flag
        )

        try:
            policy = Policy.objects.get(
                id=input.policy_id, organization=info.context.user.organization
            )

            if (
                not policy.owner
                or (
                    validate_administrator_is_empty(
                        policy.administrator, new_controls_ff_exists
                    )
                )
                or not policy.approver
            ):
                raise ServiceException('MissingPolicyOAA')

            policy.draft = get_validated_docx_file(policy)

            clean_doc_file_stream = remove_proposed_changes(policy.draft, policy.id)
            created_published_policy = PublishedPolicy.objects.create(
                published_by=info.context.user,
                owned_by=policy.owner,
                approved_by=policy.approver,
                policy=policy,
                contents=File(name=policy.draft.name, file=clean_doc_file_stream),
                comment=input.comment,
            )
            data = PublishPolicyResponseType(
                id=created_published_policy.policy.id,
                is_published=True,
                published_at=created_published_policy.created_at,
                version=created_published_policy.version,
                draft=created_published_policy.contents,
            )
            policy.is_published = True

            policy.policy_text = get_docx_file_content(policy.draft, policy.id)
            policy.save()
            # The actions items should be created only if the policy is
            # published at the first time and it's required.
            if policy.is_required:
                if PublishedPolicy.objects.filter(policy=policy).count() == 1:
                    users = policy.organization.get_users(
                        only_laika_users=True, exclude_super_admin=True
                    )
                    create_policy_action_items_by_users(users, policy)
                else:
                    update_action_items_by_policy(policy)

            generate_policy_embeddings_task.apply_async(
                args=(policy.id,),
                countdown=5,
            )
            error = ErrorType(code=None, message='')
            success = True

        except ServiceException as e:
            data = None
            error = get_publish_policy_error_message(str(e))
            success = False
        except ObjectDoesNotExist:
            data = None
            error = errors.DOES_NOT_EXIST_ERROR
            success = False
        except ValidationError:
            data = None
            error = errors.VALIDATION_ERROR
            success = False
        except Exception:
            logger.exception(
                f'Error to create published policy with ID {input.policy_id}'
            )
            data = None
            error = errors.CANNOT_PUBLISH_POLICY_ERROR
            success = False

        return PublishPolicy(success=success, error=error, data=data)


class UnpublishPolicyInput(graphene.InputObjectType):
    policy_id = graphene.String(required=True)


class UnpublishedPolicyResponseType(graphene.ObjectType):
    id = graphene.String()
    ok = graphene.Boolean()


class UnpublishPolicy(graphene.Mutation):
    class Arguments:
        input = UnpublishPolicyInput(required=True)

    success = graphene.Boolean()
    error = graphene.Field(ErrorType)
    data = graphene.Field(UnpublishedPolicyResponseType)

    @staticmethod
    @login_required
    @permission_required('policy.unpublish_policy')
    @create_revision('Unpublished policy')
    def mutate(root, info, input=None):
        data = None
        success = True
        error = None

        try:
            policy = Policy.objects.get(
                id=input.policy_id,
                organization=info.context.user.organization,
            )
            policy.is_published = False
            policy.save()

            data = UnpublishedPolicyResponseType(id=policy.id, ok=True)

            error = ErrorType(code=None, message='')
        except ObjectDoesNotExist:
            data = None
            error = errors.DOES_NOT_EXIST_ERROR
            success = False
        except ValidationError:
            data = None
            error = errors.VALIDATION_ERROR
            success = False
        except Exception:
            logger.exception(f'Error to unpublish policy with ID {input.policy_id}')
            data = None
            error = errors.CANNOT_UNPUBLISH_POLICY_ERROR
            success = False

        return UnpublishPolicy(success=success, error=error, data=data)


def delete_policies(policy_ids):
    # If the policy is deleted the action associated should be deleted too
    # Then, the policies_reviewed field should be updated too
    for policy_id in policy_ids:
        policy = Policy.objects.get(id=policy_id)
        users = policy.organization.get_users(
            only_laika_users=True, exclude_super_admin=True
        )
        policy.action_items.all().delete()
        users_to_update = []
        for user in users:
            user.policies_reviewed = are_policies_completed_by_user(user)
            user.compliant_completed = is_user_compliant_completed(user)
            users_to_update.append(user)
        User.objects.bulk_update(
            users_to_update, ['policies_reviewed', 'compliant_completed']
        )
    Policy.objects.filter(id__in=policy_ids).delete()
    error = ErrorType(code=None, message='')
    success = True
    return success, error


def get_policies_sort(order_by):
    if order_by:
        field = order_by.get('field')
        return '-' + field if order_by.get('order') == "descend" else field
    else:
        return 'display_id'


class DeletePolicy(graphene.Mutation):
    class Arguments:
        policy_id = graphene.List(graphene.UUID, required=True)

    success = graphene.Boolean()
    error = graphene.Field(ErrorType)

    @staticmethod
    @login_required
    @transaction.atomic
    @service_exception('Cannot delete policy')
    @permission_required('policy.delete_policy')
    @create_revision('Deleted policy')
    def mutate(root, info, policy_id):
        return DeletePolicy(*delete_policies(policy_id))


class DeletePolicies(graphene.Mutation):
    class Arguments:
        policy_ids = graphene.List(graphene.UUID, required=True)

    success = graphene.Boolean()
    error = graphene.Field(ErrorType)

    @staticmethod
    @login_required
    @transaction.atomic
    @service_exception('Cannot delete policies')
    @permission_required('policy.batch_delete_policy')
    @create_revision('Deleted policies')
    def mutate(root, info, policy_ids):
        return DeletePolicies(*delete_policies(policy_ids))


class UpdatePolicyInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    administrator_email = graphene.String()
    approver_email = graphene.String()
    owner_email = graphene.String()
    category = graphene.String(required=True)
    description = graphene.String(required=True)
    tags = graphene.List(graphene.String, required=False)
    is_visible_in_dataroom = graphene.Boolean(required=True)
    draft = graphene.InputField(InputFileType, required=False)
    is_required = graphene.Boolean(required=False)
    control_family_id = graphene.Int()


class UpdatePolicy(graphene.Mutation):
    class Arguments:
        id = graphene.UUID(required=True)
        input = UpdatePolicyInput(required=True)

    success = graphene.Boolean()
    error = graphene.Field(ErrorType)
    data = graphene.Field(PolicyType)

    @staticmethod
    @login_required
    @permission_required('policy.change_policy')
    @create_revision('Updated policy metadata')
    def mutate(root, info, id, input=None):
        success = True
        error = None
        data = None
        user_email = None

        try:
            with transaction.atomic():
                administrator = None
                user_email = input.get('administrator_email')
                if user_email:
                    administrator = User.objects.get(
                        email=user_email, organization=info.context.user.organization
                    )

                organization_id = info.context.user.organization_id

                administrator = get_user_by_email(
                    organization_id=organization_id,
                    email=input.get('administrator_email'),
                )
                approver = get_user_by_email(
                    organization_id=organization_id, email=input.get('approver_email')
                )
                owner = get_user_by_email(
                    organization_id=organization_id, email=input.get('owner_email')
                )

                control_family = None
                control_family_id = input.get('control_family_id')
                if control_family_id:
                    control_family = ControlPillar.objects.get(id=control_family_id)

                data, _ = Policy.objects.update_or_create(
                    id=id,
                    organization=info.context.user.organization,
                    defaults={
                        'name': input.name,
                        'category': input.category,
                        'description': input.description,
                        'administrator': administrator,
                        'approver': approver,
                        'owner': owner,
                        'is_visible_in_dataroom': input.is_visible_in_dataroom,
                        'is_required': input.is_required,
                        'control_family': control_family,
                    },
                )
                data.tags.clear()
                for tag in input.tags:
                    created_tag, _ = Tag.objects.get_or_create(
                        name=tag, organization=info.context.user.organization
                    )
                    data.tags.add(created_tag)

                if data.is_published:
                    create_or_delete_action_items_by_policy(data)
        except User.DoesNotExist:
            logger.exception(f'User with email {user_email} does not exist')
            error = errors.CANNOT_UPDATE_POLICY_ERROR
            success = False
            data = None
        except Exception:
            logger.exception(f'Error to update policy with ID {id}')
            error = errors.CANNOT_UPDATE_POLICY_ERROR
            success = False
            data = None

        return UpdatePolicy(success=success, error=error, data=data)


class RestorePolicyInput(graphene.InputObjectType):
    policy_id = graphene.String(required=True)
    version_id = graphene.Int()


class RestorePolicyResponseType(graphene.ObjectType):
    id = graphene.String()
    is_published = graphene.Boolean()
    version = graphene.String()


class RestorePolicy(graphene.Mutation):
    class Arguments:
        input = RestorePolicyInput(required=True)

    success = graphene.Boolean()
    error = graphene.Field(ErrorType)
    data = graphene.Field(RestorePolicyResponseType)

    @staticmethod
    @login_required
    @permission_required('policy.change_policy')
    @create_revision('Restored policy')
    def mutate(root, info, input=None):
        data = None
        success = True
        error = None

        try:
            published_policy = PublishedPolicy.objects.get(
                policy__id=input.policy_id, version=input.version_id
            )
            policy = Policy.objects.get(id=input.policy_id)
            policy.draft = published_policy.contents
            policy.save(generate_key=True)

            logger.info(
                f'Policy with ID {input.policy_id} '
                f'and version {input.version_id} was restored.'
            )
            data = RestorePolicyResponseType(
                id=policy.id,
                version=published_policy.version,
                is_published=policy.is_published,
            )
        except ObjectDoesNotExist:
            data = None
            error = errors.DOES_NOT_EXIST_ERROR
            success = False
        except ValidationError:
            data = None
            error = errors.VALIDATION_ERROR
            success = False
        except Exception:
            logger.exception(
                f'Error to restore policy with ID {input.policy_id} and '
                f'version {input.version_id}'
            )
            data = None
            error = errors.CANNOT_RESTORE_POLICY_ERROR
            success = False

        return RestorePolicy(success=success, error=error, data=data)


class Mutation(graphene.ObjectType):
    create_policy = CreatePolicy.Field()
    update_policy = UpdatePolicy.Field()
    publish_policy = PublishPolicy.Field()
    unpublish_policy = UnpublishPolicy.Field()
    delete_policy = DeletePolicy.Field()
    delete_policies = DeletePolicies.Field()
    restore_policy = RestorePolicy.Field()
    save_document = SavePolicyDocument.Field()
    update_onboarding_policy = UpdateOnboardingPolicy.Field()
    replace_policy = ReplacePolicy.Field()
    update_is_draf_edited = UpdateIsDraftEdited.Field()
    update_new_policy = UpdateNewPolicy.Field()

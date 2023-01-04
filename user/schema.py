import logging

import graphene
from botocore.exceptions import ClientError
from django.db import transaction
from django.db.models import Q, Value
from django.db.models.functions import Concat, Replace

import user.errors as errors
from laika.auth import login_required, permission_required
from laika.backends.concierge_backend import ConciergeAuthenticationBackend
from laika.backends.laika_backend import AuthenticationBackend
from laika.decorators import concierge_service, laika_service, service
from laika.types import ErrorType, OrderInputType, PaginationInputType
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.exceptions import ServiceException
from laika.utils.history import create_revision
from laika.utils.permissions import map_permissions
from objects.tasks import find_match_for_lo_background_check
from organization.models import Organization
from policy.utils.utils import create_policy_action_items
from user.constants import AUDITOR, CONCIERGE
from user.inputs import (
    DelegateUninvitedUserIntegrationInput,
    DelegateUserIntegrationInput,
    InviteToOrganizationInput,
    UserInput,
    UserInputEmail,
)
from user.models import Partner, User
from user.mutations import (
    ConfirmPeopleCandidates,
    DeleteUsers,
    ResendInvitation,
    SetupMFA,
    UpdateUsersPermission,
    VerifyMFA,
    delegate_uninvited_user_integration_m,
    delegate_user_integration_m,
    remove_user_m,
    update_user_email,
    update_user_m,
    user_update_preferences,
)
from user.mutations_schema import BulkInviteUser
from user.queries import (
    resolve_discovered_people_q,
    resolve_search_users_q,
    resolve_user_q,
    resolve_users_q,
)
from user.types import (
    AllUsersType,
    DiscoveredUsersResponseType,
    PartnerType,
    UserFilterInputType,
    UserIncredibleFilterInputType,
    UserResponseType,
    UsersResponseType,
    UserType,
)
from user.utils.invite_laika_user import invite_user_m
from user.utils.invite_partial_user import invite_partial_user_m

from .utils.action_items import create_quickstart_action_items
from .utils.pagination import get_pagination_result

logger = logging.getLogger('User')


def create_users_response(kwargs, users_data):
    response = {'data': users_data['users'], 'permissions': users_data['permissions']}
    if kwargs.get('pagination'):
        paginated_result = get_pagination_result(
            pagination=kwargs.get('pagination'), data=users_data['users']
        )
        pagination = exclude_dict_keys(paginated_result, ['data'])
        response['data'] = paginated_result.get('data')
        response['pagination'] = pagination

    return response


class Query(object):
    me = graphene.Field(UserResponseType)
    concierge_me = graphene.Field(UserResponseType)
    user = graphene.Field(
        UserResponseType, email=graphene.String(), id=graphene.String()
    )
    users = graphene.Field(
        UsersResponseType,
        emails=graphene.List(graphene.String),
        search_criteria=graphene.String(),
        all_users=graphene.Boolean(),
        filter=graphene.Argument(UserFilterInputType),
        filters=graphene.List(UserIncredibleFilterInputType, required=False),
        order_by=graphene.Argument(OrderInputType, required=False),
        pagination=graphene.Argument(PaginationInputType),
        exclude_super_admin=graphene.Boolean(),
        organization_id=graphene.String(required=False),
        show_deleted_users=graphene.Boolean(),
    )
    users_by_role = users
    discovered_people = graphene.Field(DiscoveredUsersResponseType)
    all_users = graphene.Field(AllUsersType, exclude_super_admin=graphene.Boolean())
    csm_and_ca_users = graphene.Field(AllUsersType)
    all_auditors = graphene.Field(AllUsersType)
    concierge_partners = graphene.List(PartnerType)

    @concierge_service(
        permission='user.view_concierge',
        exception_msg='Failed to list partners',
    )
    def resolve_concierge_partners(self, info, **kwargs):
        return Partner.objects.all()

    @concierge_service(
        permission='user.view_concierge',
        exception_msg='Failed to get csm and ca list',
        revision_name='Can view concierge',
    )
    def resolve_csm_and_ca_users(self, info, **kwargs):
        csm_and_ca_users = User.objects.filter(role=CONCIERGE)
        return AllUsersType(users=csm_and_ca_users)

    @concierge_service(
        permission='user.view_concierge',
        exception_msg='Failed to get auditor list',
        revision_name='Can view concierge',
    )
    def resolve_all_auditors(self, info, **kwargs):
        auditors = User.objects.filter(role=AUDITOR)
        return AllUsersType(users=auditors)

    @login_required
    def resolve_me(self, info, **kwargs):
        me = info.context.user
        return UserResponseType(data=me)

    @concierge_service(
        permission='user.view_concierge',
        exception_msg='Failed to retrieve me',
        revision_name='Can view concierge',
    )
    def resolve_concierge_me(self, info, **kwargs):
        me = info.context.user
        return UserResponseType(data=me)

    @login_required
    def resolve_user(self, info, **kwargs):
        try:
            user = resolve_user_q(self, info, kwargs)
            return UserResponseType(data=user)
        except Exception:
            logger.exception(errors.CANNOT_GET_USERS)
            return UserResponseType(
                error=errors.CREATE_GET_USERS_ERROR, success=False, data=None
            )

    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'user.view_user',
            },
        ],
        exception_msg='Failed to fetch list of users',
    )
    def resolve_users(self, info, **kwargs):
        try:
            search_criteria = kwargs.get('search_criteria')
            if search_criteria:
                users_data = {
                    'users': resolve_search_users_q(self, info, kwargs),
                    'permissions': [],
                }
            else:
                users_data = resolve_users_q(self, info, kwargs)

            response = create_users_response(kwargs, users_data)

            return UsersResponseType(**response)
        except Exception:
            logger.exception(errors.CANNOT_GET_USERS)
            return UsersResponseType(
                error=errors.CREATE_GET_USERS_ERROR, success=False, data=None
            )

    @concierge_service(
        permission='user.view_concierge',
        exception_msg='Failed to get concierge user list',
        revision_name='Can view concierge',
    )
    def resolve_users_by_role(self, info, **kwargs):
        try:
            search_criteria = kwargs.get('search_criteria')
            filter_args = kwargs.get('filter', {})
            roles_in = filter_args.get('roles_in', [])
            exclude_roles = filter_args.get('exclude_roles', [])
            organization_id = filter_args.get('organization_id', '')

            filter_query = Q()
            users = User.objects.annotate(
                first_name_no_spaces=Replace('first_name', Value(' '), Value('')),
                last_name_no_spaces=Replace('last_name', Value(' '), Value('')),
                full_name=Concat('first_name_no_spaces', 'last_name_no_spaces'),
            )
            if roles_in and len(roles_in) > 0:
                filter_query.add(Q(role__in=roles_in), Q.AND)
            if search_criteria:
                filter_query.add(
                    (
                        Q(full_name__icontains=search_criteria)
                        | Q(email__icontains=search_criteria)
                    ),
                    Q.AND,
                )

            if organization_id:
                organization = Organization.objects.get(id=organization_id)
                users = (
                    users.exclude(role__in=exclude_roles)
                    .filter(organization=organization)
                    .filter(filter_query)
                )
            else:
                users = users.exclude(role__in=exclude_roles).filter(filter_query)

            permissions = map_permissions(info.context.user, 'user')

            users_data = {'users': users, 'permissions': permissions}
            response = create_users_response(kwargs, users_data)

            return UsersResponseType(**response)
        except Exception:
            logger.exception(errors.CANNOT_GET_USERS)
            return UsersResponseType(
                error=errors.CREATE_GET_USERS_ERROR, success=False, data=None
            )

    @laika_service(
        permission='user.view_user', exception_msg='Cannot get user candidates'
    )
    def resolve_discovered_people(self, info, **kwargs):
        try:
            users_data = resolve_discovered_people_q(self, info, kwargs)
            response = {
                'data': users_data['users'],
            }
            return DiscoveredUsersResponseType(**response)
        except Exception:
            logger.exception(errors.CANNOT_GET_USERS)
            return DiscoveredUsersResponseType(
                error=errors.CREATE_GET_USERS_ERROR, success=False, data=None
            )

    @laika_service(
        permission='user.view_user', exception_msg='Failed to retrieve all user ids'
    )
    def resolve_all_users(self, info, **kwargs):
        try:
            users_data = resolve_users_q(self, info, kwargs)
            users = users_data['users']
            return AllUsersType(users=users)
        except Exception:
            logger.exception(errors.CANNOT_GET_USERS)
            return AllUsersType(users=users)


class InviteToOrganization(graphene.Mutation):
    class Arguments:
        input = InviteToOrganizationInput(required=True)

    success = graphene.Boolean()
    error = graphene.Field(ErrorType)
    data = graphene.Field(UserType)
    permissions = graphene.List(graphene.String)

    @staticmethod
    @login_required
    @permission_required('user.add_user')
    @create_revision('Invited user')
    def mutate(root, info, input=None):
        success = True
        error = None
        permissions = []
        try:
            with transaction.atomic():
                partial_invite = input.get('partial')
                organization = info.context.user.organization
                if partial_invite:
                    invitation_data = invite_partial_user_m(organization, input)
                else:
                    invitation_data = invite_user_m(info, input)
                data = invitation_data['data']
                if data and not partial_invite:
                    create_quickstart_action_items(data)
                    create_policy_action_items(data)
                if input.get('user_preferences'):
                    data.user_preferences.update(input.get('user_preferences'))
                    data.save()
                find_match_for_lo_background_check.delay(
                    [
                        {
                            'first_name': data.first_name,
                            'last_name': data.last_name,
                            'email': data.email,
                        }
                    ],
                    data.organization.id,
                )

                permissions = invitation_data.get('permissions', [])
        except ClientError as err:
            errors.CREATE_INVITE_USER_ERROR.message = errors.CANNOT_INVITE_USER
            logger.exception(err.response['Error'])
            success = False
            data = None
            error = errors.CREATE_INVITE_USER_ERROR
            error.message += f'. {err.response["Error"]["Message"]}'
        except Exception as err:
            errors.CREATE_INVITE_USER_ERROR.message = errors.CANNOT_INVITE_USER
            logger.exception(errors.CANNOT_INVITE_USER)
            logger.exception(err)
            success = False
            error = errors.CREATE_INVITE_USER_ERROR
            data = None
            error.message += f'. {str(err)}'
        finally:
            return InviteToOrganization(
                success=success, error=error, data=data, permissions=permissions
            )


class DelegateUserIntegration(graphene.Mutation):
    class Arguments:
        input = DelegateUserIntegrationInput(required=True)

    email = graphene.String()

    @laika_service(
        permission='user.add_user',
        exception_msg=errors.CANNOT_DELEGATE_USER_INTEGRATION,
    )
    def mutate(self, info, **kwargs):
        user = delegate_user_integration_m(info, kwargs['input'])

        return DelegateUserIntegration(email=user.email)


class DelegateUninvitedUserIntegration(graphene.Mutation):
    class Arguments:
        input = DelegateUninvitedUserIntegrationInput(required=True)

    email = graphene.String()

    @laika_service(
        permission='user.add_user',
        exception_msg=errors.CANNOT_DELEGATE_UNINVITED_USER_INTEGRATION,
    )
    def mutate(self, info, **kwargs):
        user = delegate_uninvited_user_integration_m(info, kwargs['input'])

        return DelegateUserIntegration(email=user.email)


class RemoveFromOrganization(graphene.Mutation):
    class Arguments:
        input = UserInput(required=True)

    success = graphene.Boolean()
    error = graphene.Field(ErrorType)

    @staticmethod
    @login_required
    @permission_required('user.delete_user')
    def mutate(root, info, input=None):
        success = True
        error = None
        try:
            with transaction.atomic():
                remove_user_m(info, input)
        except Exception:
            logger.exception(errors.CANNOT_REMOVE_USER)
            success = False
            error = errors.CREATE_REMOVE_USER_ERROR
        finally:
            return RemoveFromOrganization(
                success=success,
                error=error,
            )


class UpdateUser(graphene.Mutation):
    class Arguments:
        input = UserInput(required=True)

    success = graphene.Boolean()
    error = graphene.Field(ErrorType)
    data = graphene.Field(UserType)

    @staticmethod
    @login_required
    @permission_required('user.change_user')
    @create_revision('Updated user')
    def mutate(root, info, input=None):
        success = True
        error = None
        data = None
        try:
            with transaction.atomic():
                data = update_user_m(info, input)
        except Exception as e:
            logger.exception(f'{errors.CANNOT_UPDATE_USER}. {e}')
            success = False
            error = errors.CREATE_UPDATE_USER_ERROR
        finally:
            return UpdateUser(
                success=success,
                error=error,
                data=data,
            )


class UpdateUserEmail(graphene.Mutation):
    class Arguments:
        input = UserInputEmail(required=True)

    success = graphene.Boolean()
    error = graphene.Field(ErrorType)
    data = graphene.Field(UserType)

    @laika_service(
        permission='user.change_user',
        exception_msg='Failed to update user email',
        revision_name='Changed user email',
    )
    def mutate(self, info, input=None):
        success = True
        error = None
        try:
            data = update_user_email(info, input)
        except Exception as e:
            logger.exception(f'{errors.CANNOT_UPDATE_USER}. {e}')
            success = False
            error = errors.CREATE_UPDATE_USER_ERROR
            data = None

        return UpdateUserEmail(
            success=success,
            error=error,
            data=data,
        )


class UpdateUserPreferences(graphene.Mutation):
    class Arguments:
        input = UserInput(required=True)

    data = graphene.Field(UserType)

    @staticmethod
    @login_required
    @transaction.atomic
    @create_revision('Updated user')
    def mutate(root, info, input=None):
        try:
            data = user_update_preferences(info, input)
        except ServiceException:
            logger.exception(errors.CANNOT_UPDATE_PREFERENCES)

            raise ServiceException('Error updating user Preferences')

        return UpdateUserPreferences(data=data)


class Mutation(graphene.ObjectType):
    invite_to_organization = InviteToOrganization.Field()
    remove_from_organization = RemoveFromOrganization.Field()
    update_user = UpdateUser.Field()
    update_user_preferences = UpdateUserPreferences.Field()
    bulk_invite_user = BulkInviteUser.Field()
    delete_users = DeleteUsers.Field()
    update_users_permission = UpdateUsersPermission.Field()
    confirm_people_candidates = ConfirmPeopleCandidates.Field()
    setup_mfa = SetupMFA.Field()
    verify_mfa = VerifyMFA.Field()
    update_user_email = UpdateUserEmail.Field()
    resend_invitation = ResendInvitation.Field()
    delegate_user_integration = DelegateUserIntegration.Field()
    delegate_uninvited_user_integration = DelegateUninvitedUserIntegration.Field()

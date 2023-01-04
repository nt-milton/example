import logging
from typing import Dict

import graphene
from botocore.exceptions import BotoCoreError, ClientError

import user.errors as errors
from feature.constants import okta_feature_flag, sso_feature_flag
from laika.auth import login_required
from laika.aws.cognito import (
    associate_token,
    change_mfa_preference,
    delete_cognito_users,
    get_user,
    update_user_attributes,
    update_user_group,
    verify_token,
)
from laika.aws.ses import send_email_with_cc
from laika.constants import OKTA
from laika.decorators import laika_service
from laika.okta.api import OktaApi
from laika.settings import LAIKA_WEB_REDIRECT, MAIN_ARCHIVE_MAIL
from laika.utils.exceptions import ServiceException
from objects.models import Attribute, LaikaObjectType
from objects.tasks import find_match_for_lo_background_check
from user.constants import (
    ALL_HEADERS,
    AUDITOR,
    AUDITOR_ROLES,
    HEADER_BULK_USERS,
    INVITATION_TYPES,
    ROLE_ADMIN,
    ROLE_MEMBER,
    USER_ROLES,
)
from user.helpers import (
    assign_user_to_organization_vendor_stakeholders,
    manage_cognito_user,
    manage_okta_user,
)
from user.permissions import change_user_permissions_group
from user.utils.invite_laika_user import invite_user_m

from .inputs import ConfirmUserPermissionInput, UpdateUserPermissionInput
from .models import DISCOVERY_STATE_CONFIRMED, DISCOVERY_STATE_IGNORED, User
from .utils.email import get_delegation_path

logger = logging.getLogger(__name__)

HEADER_NAMES = [header['name'] for header in ALL_HEADERS]
HEADER_NAMES_BULK_USERS = [header['name'] for header in HEADER_BULK_USERS]
MAX_ROWS = 500
HEADER_ROW = 2
USERS_START = 3
ICON_NAME = 'group'
ICON_COLOR = 'brandViolet'

okta_api = OktaApi()


def remove_user_m(info, input):
    current_user = info.context.user
    email = input['email']
    User.objects.get(email=email, organization_id=current_user.organization_id).delete()

    delete_cognito_users([email])


def can_update_cognito_attributes(user_input, user):
    return (
        user_input.get('first_name') or user_input.get('last_name')
    ) and user.is_active


def can_update_manager(user_input, manager_email):
    return 'manager_email' in user_input or manager_email


def get_old_and_new_cognito_role(user, old_role, new_role):
    cognito_new_role = new_role
    cognito_old_role = old_role
    if user.role in AUDITOR_ROLES.values() and new_role not in AUDITOR_ROLES.values():
        cognito_new_role = AUDITOR
    elif user.role not in AUDITOR_ROLES.values():
        if new_role != ROLE_ADMIN:
            cognito_new_role = ROLE_MEMBER

        if old_role != ROLE_ADMIN:
            cognito_old_role = ROLE_MEMBER
    return cognito_old_role, cognito_new_role


def update_user_cognito_group(user, new_role, old_role):
    is_role_update_required = new_role and old_role.lower() != new_role.lower()

    if is_role_update_required and user.is_active:
        cognito_old_role, cognito_new_role = get_old_and_new_cognito_role(
            user=user, old_role=old_role, new_role=new_role
        )
        update_user_group(user.email, cognito_old_role, cognito_new_role)


def update_user_email(info, input):
    current_user = info.context.user
    can_update_user = current_user.has_perm('user.change_user')

    if not can_update_user:
        raise ServiceException(errors.ACCESS_DENIED)

    email = input.get('currentEmail')
    if not email:
        raise ServiceException(errors.MISSING_REQUIRED_FIELDS)

    new_email = input.get('newEmail')
    if not new_email:
        raise ServiceException(errors.MISSING_REQUIRED_FIELDS)

    user = User.objects.get(email=email, organization=info.context.user.organization)

    if user.is_active:
        raise ServiceException(errors.CANNOT_UPDATE_USER)

    user.email = new_email
    user.save()

    return user


def update_user_m(info, input):
    current_user = info.context.user
    can_update_user = current_user.has_perm('user.change_user')
    organization = info.context.user.organization
    has_preferences = input.get('user_preferences')
    email = input.get('email')

    if has_preferences:
        raise ServiceException(errors.INVALID_OPERATION)

    if not can_update_user:
        raise ServiceException(errors.ACCESS_DENIED)

    if not email:
        raise ServiceException(errors.MISSING_REQUIRED_FIELDS)

    user = User.objects.get(email=email, organization_id=organization.id)

    old_role = user.role
    new_role = input.get('role')

    manager_email = input.get('manager_email', '')
    if can_update_manager(input, manager_email):
        logger.info('Manager can update')
        manager = User.objects.get(email=manager_email, organization_id=organization.id)

        user.manager = manager

    for attribute_name, attribute_value in input.items():
        setattr(user, attribute_name, attribute_value)
    user.save()

    should_update_role = new_role and old_role.lower() != new_role.lower()
    if should_update_role and user.is_active:
        change_user_permissions_group(old_role, new_role, user)

    if organization.is_flag_active(okta_feature_flag):
        logger.info(f'Organization: {organization} has okta flag')
        update_okta_user(updated_user=user)

    if get_user(user.email):
        logger.info('Updating cognito user')
        update_cognito_user(user, input, new_role, old_role)

    return user


def update_okta_user(updated_user: User):
    if updated_user.organization.is_flag_active(sso_feature_flag):
        logger.info(
            'Cannot update user because organization:'
            f' {updated_user.organization} has SSO flag'
        )
        return

    okta_user = okta_api.get_user_by_email(updated_user.email)
    if okta_user and okta_user.credentials.provider.type == OKTA:
        try:
            okta_api.update_user(okta_user, updated_user)
        except Exception as e:
            logger.warning(f'Error trying to update okta user in mutation: {e}')
    else:
        logger.info('User profile can not be updated because is federated')


def update_cognito_user(updated_user: User, user_input, new_role, old_role):
    try:
        update_user_cognito_group(updated_user, new_role, old_role)

        if can_update_cognito_attributes(user_input, updated_user):
            update_fields = {
                'last_name': updated_user.last_name,
                'first_name': updated_user.first_name,
            }
            update_user_attributes(updated_user.email, update_fields)

    except Exception as e:
        logger.exception(f'Error trying to update cognito user in mutation: {e}')
        raise e


def cleanup_invalid_user_filter_preferences(filters: Dict, organization) -> Dict:
    cleaned_filters = dict()
    for current_lo_type, values in filters.items():
        lo_type = LaikaObjectType.objects.filter(
            type_name=current_lo_type, organization=organization
        ).first()

        if lo_type:
            attributes = {
                attribute.name
                for attribute in Attribute.objects.filter(object_type_id=lo_type.id)
            }
            filter_attributes = [value['column'] for value in values]
            if any(
                [True if value in attributes else False for value in filter_attributes]
            ):
                cleaned_filters[current_lo_type] = values
        else:
            logger.info(
                f'{current_lo_type} in filters is not found in Laika Object Types.\n'
            )

    return cleaned_filters


def user_update_preferences(info, input):
    email = input.get('email')
    if not email:
        raise ServiceException(errors.MISSING_REQUIRED_FIELDS)

    user = User.objects.get(email=email, organization=info.context.user.organization)

    if user.id != info.context.user.id:
        raise ServiceException('User does not match authenticated user')

    user.user_preferences = input.get('user_preferences')

    if 'laikaObjectsFilter' in user.user_preferences:
        user_filters = cleanup_invalid_user_filter_preferences(
            user.user_preferences['laikaObjectsFilter'], info.context.user.organization
        )
        user.user_preferences['laikaObjectsFilter'] = user_filters

    user.save()

    return user


def delegate_user_integration_m(info, input):
    email = input.get('email')
    vendor_id = input.get('vendor_id')
    category = input.get('category')

    from_user = info.context.user
    organization = info.context.user.organization
    delegated_user = User.objects.get(email=email)
    organization_vendor = organization.organization_vendors.filter(
        vendor_id=vendor_id
    ).last()

    integration_name = (
        organization_vendor.vendor.name if organization_vendor else category
    )

    template_context = {
        'subject': (
            f'{from_user.first_name} {from_user.last_name} assigned you a compliance'
            ' task'
        ),
        'first_name': delegated_user.first_name,
        'last_name': delegated_user.last_name,
        'from_first_name': from_user.first_name,
        'from_last_name': from_user.last_name,
        'org_name': organization.name,
        'integration_name': integration_name,
        'login_link': f'{LAIKA_WEB_REDIRECT}{get_delegation_path(organization.state)}',
    }

    send_email_with_cc(
        subject=template_context['subject'],
        from_email=from_user.email,
        to=[delegated_user.email],
        template='onboarding_delegate_integration.html',
        template_context=template_context,
        cc=[organization.customer_success_manager_user.email],
        bbc=[MAIN_ARCHIVE_MAIL],
    )

    if organization_vendor:
        assign_user_to_organization_vendor_stakeholders(
            organization_vendor, delegated_user
        )

    return delegated_user


def delegate_uninvited_user_integration_m(info, input):
    first_name = input.get('first_name')
    last_name = input.get('last_name')
    email = input.get('email')
    vendor_id = input.get('vendor_id')
    category = input.get('category')

    organization = info.context.user.organization
    from_user = info.context.user

    organization_vendor = organization.organization_vendors.filter(
        vendor_id=vendor_id
    ).last()

    integration_name = (
        organization_vendor.vendor.name if organization_vendor else category
    )

    template_context = {
        'subject': (
            f'{from_user.first_name} {from_user.last_name} assigned you a compliance'
            ' task'
        ),
        'first_name': first_name,
        'last_name': last_name,
        'from_first_name': from_user.first_name,
        'from_last_name': from_user.last_name,
        'org_name': organization.name,
        'integration_name': integration_name,
        # extra context to invite_user_m #
        'email': email,
        'cc': [organization.customer_success_manager_user.email],
        'bbc': [MAIN_ARCHIVE_MAIL],
        'role': 'OrganizationAdmin',
        'organization_id': organization.id,
        'invitation_type': INVITATION_TYPES['DELEGATION'],
        # extra context to invite_user_m #
    }

    data = invite_user_m(info, template_context)

    invited_user = data.get('data')

    if organization_vendor:
        assign_user_to_organization_vendor_stakeholders(
            organization_vendor, invited_user
        )

    return invited_user


class DeleteUsers(graphene.Mutation):
    class Arguments:
        input = graphene.List(graphene.String, required=True)

    deleted = graphene.List(graphene.String)

    @staticmethod
    @laika_service(
        permission='user.delete_user',
        exception_msg='Failed to delete users. Please try again',
        revision_name='Delete users',
    )
    def mutate(root, info, **kwargs):
        organization = info.context.user.organization
        users_to_delete = kwargs['input']
        if info.context.user.email in users_to_delete:
            users_to_delete.remove(info.context.user.email)

        User.objects.filter(
            email__in=users_to_delete, organization=organization
        ).delete()

        return DeleteUsers(deleted=users_to_delete)


class UpdateUsersPermission(graphene.Mutation):
    class Arguments:
        input = UpdateUserPermissionInput(required=True)

    updated_users = graphene.List(graphene.String)
    role = graphene.String()

    @staticmethod
    @laika_service(
        permission='user.change_user',
        exception_msg='Failed to update users permission. Please try again',
        revision_name='Update users permission',
    )
    def mutate(root, info, **kwargs):
        organization = info.context.user.organization
        users_input = kwargs['input']
        emails = users_input.get('emails')

        users = User.objects.filter(organization=organization, email__in=emails).all()

        new_role = users_input.get('role')
        users_to_update = []
        users_with_old_role = []
        for u in users:
            if u.role != new_role:
                old_user = {'id': u.id, 'role': u.role}
                users_with_old_role.append(old_user)
                u.role = new_role
                users_to_update.append(u)

        User.objects.bulk_update(users_to_update, ['role'])

        for u in users_to_update:
            old_role = [
                ou.get('role') for ou in users_with_old_role if ou.get('id') == u.id
            ][0]
            update_user_cognito_group(u, new_role, old_role)

        return UpdateUsersPermission(updated_users=emails, role=new_role)


class ConfirmPeopleCandidates(graphene.Mutation):
    class Arguments:
        confirmed_people_candidates = graphene.List(ConfirmUserPermissionInput)
        ignored_people_emails = graphene.List(graphene.NonNull(graphene.String))

    people_emails = graphene.List(graphene.NonNull(graphene.String))

    @laika_service(permission='user.add_user', exception_msg='Failed to confirm user')
    def mutate(self, info, confirmed_people_candidates, ignored_people_emails):
        organization = info.context.user.organization
        people_emails = []
        users_info = []
        for confirmed_candidate in confirmed_people_candidates:
            user = User.objects.filter(
                email=confirmed_candidate['email'], organization=organization
            ).first()
            if user:
                if confirmed_candidate['role'] in USER_ROLES.values():
                    confirmed_candidate['organization_id'] = str(organization.id)
                    confirmed_candidate['email'] = user.email
                    confirmed_candidate['last_name'] = user.last_name
                    confirmed_candidate['first_name'] = user.first_name
                    invite_user_m(info, confirmed_candidate, True)
                users_info.append(
                    {
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'email': user.email,
                    }
                )
                people_emails.append(user.email)
        User.objects.filter(email__in=people_emails, organization=organization).update(
            discovery_state=DISCOVERY_STATE_CONFIRMED
        )
        User.objects.filter(
            email__in=ignored_people_emails, organization=organization
        ).update(discovery_state=DISCOVERY_STATE_IGNORED)
        find_match_for_lo_background_check.delay(users_info, organization.id)
        return ConfirmPeopleCandidates(people_emails=people_emails)


class SetupMFA(graphene.Mutation):
    class Arguments:
        access_token = graphene.String(required=True)

    secret = graphene.String()

    @login_required
    def mutate(self, info, access_token):
        return SetupMFA(associate_token(access_token))


class VerifyMFA(graphene.Mutation):
    class Arguments:
        access_token = graphene.String(required=True)
        code = graphene.String(required=True)

    mfa = graphene.Boolean()

    @login_required
    def mutate(self, info, access_token, code):
        user = info.context.user
        try:
            response = verify_token(access_token, code)
            if response.get('Status') != 'SUCCESS':
                raise ServiceException('Error validating MFA')
            change_mfa_preference(user.username, True)
            user.mfa = True
            user.save()
            return VerifyMFA(True)
        except (BotoCoreError, ClientError):
            raise ServiceException('Error validating MFA')


class ResendInvitation(graphene.Mutation):
    class Arguments:
        email = graphene.String(required=True)

    success = graphene.Boolean()

    @laika_service(
        permission='user.add_user', exception_msg='Failed to resend invitation to user'
    )
    def mutate(self, info, email):
        try:
            user = User.objects.get(email=email)
            is_okta_active = user.organization.is_flag_active(okta_feature_flag)

            if is_okta_active:
                manage_okta_user(user)
            else:
                manage_cognito_user(user)

            return ResendInvitation(success=True)
        except Exception:
            raise ServiceException('Error resending invitation')

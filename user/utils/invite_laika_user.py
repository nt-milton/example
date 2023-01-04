import logging

import django.utils.timezone as timezone

import user.errors as errors
from feature.constants import okta_feature_flag
from laika.aws.cognito import create_user
from laika.constants import COGNITO, OKTA
from laika.okta.api import OktaApi
from laika.settings import ENVIRONMENT, LAIKA_BACKEND
from laika.utils.exceptions import ServiceException
from laika.utils.permissions import map_permissions
from organization.errors import ORGANIZATION_NOT_FOUND
from organization.models import Organization
from user.constants import (
    INVITATION_DAYS_TO_EXPIRE,
    INVITATION_TYPES,
    OKTA_GROUPS_NAMES,
    ROLE_ADMIN,
    ROLE_MEMBER,
    USER_ROLES,
)
from user.models import MagicLink, User
from user.permissions import add_user_to_group
from user.utils.parse_user import map_choices_to_dic_inverted, parse_user_fields

from .email import send_invite_email

logger = logging.getLogger(__name__)
OktaApi = OktaApi()


def send_invite(payload):
    email = payload.get('email')
    name = payload.get('name')
    role = payload.get('role')
    temporary_password = payload.get('password')

    user = User.objects.filter(email=email).first()
    token = ''
    if user:
        magic_link = MagicLink.objects.update_or_create(
            user=user, defaults={'temporary_code': temporary_password}
        )[0]
        token = magic_link.token

    roles_by_value = map_choices_to_dic_inverted(USER_ROLES.items())
    formatted_role = roles_by_value.get(role, '').replace('_', ' ').title()

    email_context = {
        **payload,
        'name': name,
        'title': 'You are invited to Laika',
        'hero_title': 'Welcome to Laika!',
        'hero_subtitle': 'Experience the new way to do compliance!',
        'username': email,
        'password': temporary_password,
        'magic_token': token,
        'message': payload.get('message'),
        'role': formatted_role,
        'idp': payload.get('idp'),
        'expire_days': INVITATION_DAYS_TO_EXPIRE,
    }
    if payload.get('invitation_type') == INVITATION_TYPES['DELEGATION']:
        email_context['organization_state'] = user.organization.state
    send_invite_email(email, email_context)


def get_email_content(info, input_data):
    name = info.context.user.get_full_name() if info else ''
    message = ''
    if input_data.get('show_inviter_name'):
        message = input_data.get('message', '')
    return name, message


def invite_user_m(info, input, invite_from_seeder=False):
    user_org = Organization.objects.get(pk=input.get('organization_id'))

    if user_org is None:
        raise Exception(ORGANIZATION_NOT_FOUND)

    user_is_not_in_organization = (
        not invite_from_seeder
        and input.get('organization_id') != info.context.user.organization.id
    )

    if not invite_from_seeder and user_is_not_in_organization:
        raise Exception(errors.NO_ORGANIZATION_USER)

    if not input.get('role') in USER_ROLES.values():
        email = input.get('email')
        raise ServiceException(f'Invalid role for user {email}')

    existing_user = User.objects.filter(
        email=input.get('email', '').lower(),
        organization_id=input.get('organization_id'),
    ).first()

    if existing_user and existing_user.is_active:
        logger.warning(f'User already exists with ID: {existing_user.id}')
        raise Exception(errors.USER_EXISTS)

    is_okta_active = user_org.is_flag_active(okta_feature_flag)

    if is_okta_active:
        okta_user = OktaApi.get_user_by_email(input.get('email'))
        if okta_user:
            logger.info(f'Deleting existing okta user {okta_user}')
            OktaApi.delete_user(okta_user.id)

        user_groups = OKTA_GROUPS_NAMES[str(ENVIRONMENT)][LAIKA_BACKEND]

        idp_user, user_temporary_password = OktaApi.create_user(
            first_name=input.get('first_name'),
            last_name=input.get('last_name'),
            email=input.get('email'),
            login=input.get('email'),
            organization=user_org,
            user_groups=user_groups,
        )

        idp_username = idp_user.id
    else:
        cognito_role = input.get('role', ROLE_MEMBER)

        if cognito_role != ROLE_ADMIN:
            cognito_role = ROLE_MEMBER

        create_user_data = {
            'role': cognito_role,
            'email': input.get('email', '').lower(),
            'last_name': input.get('last_name'),
            'first_name': input.get('first_name'),
            'organization_id': user_org.id,
            'tier': user_org.tier,
            'organization_name': user_org.name,
        }

        cognito_user = create_user(create_user_data)
        idp_username = cognito_user.get('username')
        user_temporary_password = cognito_user.get('temporary_password')

    # This is because when some data is imported the users related might
    # not been created yet. So in those cases a partial user is created and
    # here they are updated when officially added from the system.
    people_data = parse_user_fields(user_org, {**input, 'username': idp_username})

    data, _ = User.objects.update_or_create(
        email=people_data.get('email'),
        organization_id=people_data.get('organization_id'),
        defaults={
            **people_data,
            'is_active': True,
            'invitation_sent': timezone.now(),
            'deleted_at': None,
        },
    )
    add_user_to_group(data)

    permissions = []
    if not invite_from_seeder:
        permissions = map_permissions(info.context.user, 'user', [data])

    name, message = get_email_content(info, input)
    send_invite(
        {
            **input,
            'email': input.get('email'),
            'name': name,
            'message': message,
            'password': user_temporary_password,
            'role': input.get('role'),
            'idp': OKTA if is_okta_active else COGNITO,
        }
    )

    return {'data': data, 'permissions': permissions}

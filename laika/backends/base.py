import logging
from datetime import datetime
from typing import Mapping, Optional

import jwt
import pytz
from asgiref.sync import sync_to_async
from okta.models import User as OktaUser

from laika.aws.cognito import COGNITO_KEYS, decode_token
from laika.constants import AUTH_GROUPS, COGNITO, CUSTOM_ORGANIZATION_ID_CLAIM, OKTA
from laika.okta.api import OktaApi
from laika.okta.auth import ROLE, decode_okta, decode_okta_async, is_issued_by_okta
from laika.settings import (
    AUDITS_BACKEND,
    CONCIERGE_BACKEND,
    DJANGO_SETTINGS,
    ENVIRONMENT,
    LAIKA_BACKEND,
    OPEN_API_SECRET,
)
from laika.utils.exceptions import ServiceException
from organization.models import ApiTokenHistory, Organization
from user.constants import (
    AUDITOR,
    AUDITOR_ADMIN,
    COGNITO_ROLE_GROUPS,
    CONCIERGE,
    OKTA_APPS_NAMES,
    OKTA_ROLES,
    ROLE_VIEWER,
)
from user.models import User
from user.permissions import add_user_to_group

logger = logging.getLogger(__name__)

OktaApi = OktaApi()

KEY_ERROR = 'Token with unexpected key'
PRODUCTION = 'prod'


def backend_authenticate(backend, **kwargs) -> Optional[User]:
    user = authenticate(
        selected_backend=backend,
        token=kwargs.get('token'),
        verify_exp=kwargs.get('verify_exp') or True,
    )

    if not user:
        return None

    if backend == kwargs.get('expected_backend'):
        logger.info(f'✅ {backend} authenticated by user: {user.id} ')
        return user
    else:
        return None


def authenticate(
    selected_backend: str, token, verify_exp: bool = True  # for testing purposes only
) -> Optional[User]:
    if not token:
        return None

    decoded_token = decode_jwt(token, verify_exp)
    if not decoded_token or not decoded_token['idp']:
        return None

    logger.info('✅ Token decoded successfully')

    if decoded_token['idp'] == OKTA and token_meets_apps(
        decoded_token, selected_backend
    ):
        logger.info('🔥 OKTA Token')
    elif decoded_token['idp'] == COGNITO and token_meets_roles(
        decoded_token, selected_backend
    ):
        logger.info('🔥 COGNITO Token')
    else:
        return None

    user = validate_internal_user_per_backend(
        get_internal_user(decoded_token), selected_backend
    )
    auth_time = datetime.fromtimestamp(decoded_token['auth_time'], pytz.timezone('UTC'))
    if user.last_login != auth_time:
        user.last_login = auth_time
        user.save()

    return user


def decode_jwt(token: str, verify_exp=True):
    try:
        kid = get_kid(token)
        if not kid or not token:
            return None
        if is_issued_by_okta(token):
            return decode_okta(token, verify_exp=verify_exp)
        elif is_cognito_token(kid):
            return decode_token(token, verify_exp=verify_exp)
        raise jwt.exceptions.InvalidKeyError(KEY_ERROR)  # type: ignore
    except Exception as e:
        logger.exception(f'error while decoding jwt token {e}')
        raise e


def parse_api_token(token: str):
    try:
        token_spread = token.split(' ') if isinstance(token, str) else ['']
        keyword = token_spread[0]
        if keyword == 'APIKey' and len(token_spread) > 1:
            return True, token_spread[1]
    except Exception:
        logger.warning('Error trying to parse api token')
    return False, ''


def decode_api_token(token: str):
    payload = jwt.decode(token, OPEN_API_SECRET)
    user_email = payload.get('email', '')
    token_id = payload.get('uuid', '')
    token_record = ApiTokenHistory.all_objects.get(token_identifier=token_id)
    if user_email and token_record.is_active:
        return payload
    raise ServiceException('Error decoding api token')


async def decode_jwt_async(token: str, verify_exp=True):
    try:
        is_api_token, api_token = parse_api_token(token)
        if is_api_token:
            return await sync_to_async(decode_api_token)(api_token)
        elif is_issued_by_okta(token):
            decoded_token = await decode_okta_async(token, verify_exp=verify_exp)

            return decoded_token
        elif is_cognito_token(get_kid(token)):
            return decode_token(token, verify_exp=verify_exp)
        raise jwt.exceptions.InvalidKeyError(KEY_ERROR)  # type: ignore
    except Exception as e:
        logger.exception(f'error while decoding jwt token async {e}')
        raise e


def get_internal_user(decoded_token):
    email = decoded_token['email']
    idp = decoded_token['idp']

    if is_legacy_super_admin(email) and idp == COGNITO:
        return get_django_user(decoded_token['username'])

    user = User.objects.filter(email__iexact=email).first()
    if not user:
        logger.warning('User does not exist in database')
        user = create_internal_user_based_on_token(decoded_token)

        if not user:
            logger.exception(f'Failed creating internal user from token: {user.email}')
            return None

    if not user.username or user.username != decoded_token['username']:
        logger.warning(
            f'User with ID: {user.id} does not have an username or it was different'
        )
        user.username = decoded_token['username']
        user.save()

    if decoded_token.get(ROLE) and user.role != OKTA_ROLES.get(decoded_token.get(ROLE)):
        logger.info(f'Updating role:{user.id} {OKTA_ROLES[decoded_token[ROLE]]}')
        user.role = OKTA_ROLES[decoded_token[ROLE]]
        user.save()

    if not user.groups.all():
        logger.warning(f'User with ID: {user.id} does not have a group')
        add_user_to_group(user)

    if not user.is_active:
        logger.warning(f'User with ID: {user.id} is not active')
        user.is_active = True
        user.save()

    logger.info(f'User found, ID: {user.id}')
    return user


def validate_internal_user_per_backend(user: User, selected_backend: str):
    if not user:
        return None

    validate_user_per_backend = {
        f'{LAIKA_BACKEND}': validate_laika_user,
        f'{CONCIERGE_BACKEND}': validate_concierge_user,
        f'{AUDITS_BACKEND}': validate_audits_user,
    }

    validate_user = validate_user_per_backend[selected_backend]
    return validate_user(user) if validate_user else None


def validate_laika_user(user: User):
    if not user.organization:
        logger.warning('User has not organization')
        return None
    return user


def validate_concierge_user(user: User):
    if not user.role == CONCIERGE:
        logger.warning(f'User has not role {CONCIERGE}')
        return None
    return user


def validate_audits_user(user: User):
    if user.role not in (AUDITOR, AUDITOR_ADMIN):
        logger.warning(f'User has not role in {(AUDITOR, AUDITOR_ADMIN)}')
        return None
    return user


def get_organization_from_okta_user(user: OktaUser):
    if not user.profile.organization_id:
        logger.warning('user profile has not organization attribute')
        return None

    return Organization.objects.filter(id=user.profile.organization_id).first()


def create_internal_user_from_cognito_token(decoded_token):
    organization_id = decoded_token[CUSTOM_ORGANIZATION_ID_CLAIM]
    cognito_role = decoded_token[AUTH_GROUPS][0]

    if not organization_id or not cognito_role:
        logger.warning('Organization Id or role from cognito token not found')
        return None

    organization = Organization.objects.get(id=organization_id)
    logger.info(
        'Trying to create a new internal user. From cognito token '
        f'Organization selected: {organization}'
    )

    internal_user, _ = User.objects.get_or_create(
        first_name=decoded_token['name'],
        last_name=decoded_token['family_name'],
        email=decoded_token['email'],
        username=decoded_token['username'],
        role=cognito_role,
        is_active=True,
        organization=organization,
    )

    add_user_to_group(internal_user)

    logger.info(f'Internal user id: {internal_user.id} created successfully')
    return internal_user


def create_internal_user_based_on_token(decoded_token) -> Optional[User]:
    if decoded_token['idp'] == COGNITO:
        logger.info(f'Cognito Token: {decoded_token}')
        return create_internal_user_from_cognito_token(decoded_token)
    elif decoded_token['idp'] == OKTA:
        logger.info(f'Okta Token: {decoded_token}')
        user = OktaApi.get_user_by_email(decoded_token['email'])
        if not user:
            logger.error('User not found within OKTA instance')
            return None

        organization = get_organization_from_okta_user(user)
        if not organization:
            logger.warning('Organization UUID from token not found in db')
            return None

        logger.info(
            'Trying to create a new internal user. '
            f'Organization selected: {organization}'
        )

        role = ROLE_VIEWER
        if hasattr(user.profile, 'laika_role') and user.profile.laika_role:
            role = OKTA_ROLES.get(user.profile.laika_role, ROLE_VIEWER)

        internal_user, _ = User.objects.get_or_create(
            first_name=user.profile.first_name,
            last_name=user.profile.last_name,
            email=user.profile.email,
            username=user.id,
            role=role,
            is_active=True,
            organization=organization,
        )

        add_user_to_group(internal_user)

        logger.info(f'Internal user id: {internal_user.id} created successfully')
        return internal_user
    else:
        return None


def get_kid(token: str) -> str:
    try:
        return jwt.get_unverified_header(token).get('kid')
    except Exception as e:
        logger.exception(f'Error getting token unverified header: {e}')
        return ''


def is_cognito_token(kid: str) -> bool:
    return kid in COGNITO_KEYS if kid else False


def get_django_user(username: str) -> User:
    return User.objects.filter(username=username).first()


def is_legacy_super_admin(email: str) -> bool:
    return email == DJANGO_SETTINGS.get('LEGACY_SUPERADMIN')


def token_meets_apps(decoded_token: Mapping, selected_backend: str) -> bool:
    intersection = set(decoded_token[AUTH_GROUPS]).intersection(
        OKTA_APPS_NAMES[str(ENVIRONMENT)][selected_backend]
    )

    return len(intersection) > 0


def token_meets_roles(decoded_token: Mapping, selected_backend: str) -> bool:
    intersection = set(decoded_token[AUTH_GROUPS]).intersection(
        COGNITO_ROLE_GROUPS[selected_backend]
    )

    return len(intersection) > 0

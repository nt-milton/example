import json
import logging
import os
from json.decoder import JSONDecodeError

import boto3
import jwt
import requests

from laika.aws.secrets import REGION_NAME
from laika.constants import AUTH_GROUPS, COGNITO, COGNITO_GROUPS, COGNITO_USERNAME
from laika.settings import AWS_REGION, DJANGO_SETTINGS
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.exceptions import ServiceException
from laika.utils.strings import get_temporary_random_password
from user.constants import USER_ROLES
from user.utils.email import format_super_admin_email

logger = logging.getLogger('Cognito User')

LEGACY_AWS_ACCESS_KEY = os.getenv('LEGACY_AWS_ACCESS_KEY')
LEGACY_AWS_SECRET_ACCESS_KEY = os.getenv('LEGACY_AWS_SECRET_ACCESS_KEY')
USER_POOL_ID = DJANGO_SETTINGS.get('LEGACY_POOL_ID')

session = boto3.session.Session()
cognito = session.client(
    'cognito-idp',
    region_name=REGION_NAME,
    aws_access_key_id=LEGACY_AWS_ACCESS_KEY,
    aws_secret_access_key=LEGACY_AWS_SECRET_ACCESS_KEY,
)


def client():
    return cognito


def _first_matching_name_in_list(name, elements, default=None):
    return next(
        iter([e.get('Value') for e in elements if e.get('Name') == name]), default
    )


def _get_user_created_info(user_created):
    user = user_created.get('User')
    attributes = user.get('Attributes')
    return {
        'username': user.get('Username', user),
        'email': _first_matching_name_in_list('email', attributes),
        'first_name': _first_matching_name_in_list('name', attributes),
        'last_name': _first_matching_name_in_list('family_name', attributes),
        'role': user_created.get('role'),
        'organization_id': _first_matching_name_in_list(
            'custom:organizationId', attributes
        ),
        'organization_tier': _first_matching_name_in_list(
            'custom:organizationTier', attributes
        ),
        'organization_name': _first_matching_name_in_list(
            'custom:organizationName', attributes
        ),
        'temporary_password': user_created.get('temporary_password'),
    }


def add_user_to_group(user_name, group_name):
    logger.info(
        'Cognito add user to groupusername: {} group_name: {}'.format(
            user_name, group_name
        )
    )
    return cognito.admin_add_user_to_group(
        Username=user_name.lower(), GroupName=group_name, UserPoolId=USER_POOL_ID
    )


def _get_create_user_params(creation_data):
    email = creation_data.get('email', '').lower()
    organization_params = []
    if creation_data.get("organization_id"):
        organization_params = [
            {
                'Name': 'custom:organizationId',
                'Value': f'{creation_data.get("organization_id")}',
            },
            {'Name': 'custom:organizationTier', 'Value': creation_data.get('tier')},
            {
                'Name': 'custom:organizationName',
                'Value': creation_data.get('organization_name'),
            },
        ]

    create_user_params = {
        'UserPoolId': USER_POOL_ID,
        'Username': email,
        'TemporaryPassword': creation_data.get('temporary_password'),
        'UserAttributes': [
            {'Name': 'email_verified', 'Value': 'true'},
            {'Name': 'email', 'Value': email},
            {
                'Name': 'family_name',
                'Value': creation_data.get('last_name', '').lower(),
            },
            {'Name': 'name', 'Value': creation_data.get('first_name', '').lower()},
            *organization_params,
        ],
        'MessageAction': 'SUPPRESS',
    }

    logger.info(
        'Create cognito user username: {} organization: {}'.format(
            email, creation_data.get("organization_id")
        )
    )
    return create_user_params


def create_user(create_user_data):
    logger.info(f'Create cognito user with data {create_user_data}')

    temporary_password = get_temporary_random_password()
    create_user_params = _get_create_user_params(
        {**create_user_data, 'temporary_password': temporary_password}
    )
    cognito_user_reponse = cognito.admin_create_user(**create_user_params)
    role = create_user_data.get('role')
    user_created = {
        **cognito_user_reponse,
        'temporary_password': temporary_password,
        'role': role,
    }
    add_user_to_group(user_created.get('User').get('Username'), role)

    return _get_user_created_info(user_created)


def get_user(username: str):
    try:
        return cognito.admin_get_user(UserPoolId=USER_POOL_ID, Username=username)
    except cognito.exceptions.UserNotFoundException:
        logger.warning(f'Tried to get cognito user: {username} was not found')
        return None


def create_super_admin(create_user_data):
    cognito_super_admin = get_user(create_user_data['email'])
    website = create_user_data.get('website')
    attributes = cognito_super_admin.get('UserAttributes')
    email = _first_matching_name_in_list('email', attributes)

    logger.info(
        'Create organization cognito super admin '
        f'cognito_super_admin: {email} '
        f'organization_id: {create_user_data.get("organization_id")}'
    )

    creation_data = {
        'role': USER_ROLES.get('SUPER_ADMIN'),
        'email': format_super_admin_email(email, website),
        'last_name': _first_matching_name_in_list('family_name', attributes),
        'first_name': _first_matching_name_in_list('name', attributes),
        'organization_id': create_user_data.get('organization_id'),
        'tier': create_user_data.get('tier'),
        'organization_name': create_user_data.get('organization_name'),
    }
    user = create_user(creation_data)

    logger.info(f'Super admin created user: {user}')
    return user


def disable_cognito_users(emails):
    for email in emails:
        logger.info(f'Disabling cognito username: {email}')
        try:
            cognito.admin_disable_user(UserPoolId=USER_POOL_ID, Username=email.lower())
        except cognito.exceptions.UserNotFoundException:
            logger.warning(
                f'Tried to disable Cognito user username: {email} and was not found'
            )


def enable_cognito_users(emails):
    for email in emails:
        logger.info(f'Enabling cognito username: {email}')
        try:
            cognito.admin_enable_user(UserPoolId=USER_POOL_ID, Username=email.lower())
        except cognito.exceptions.UserNotFoundException:
            logger.warning(
                f'Tried to enable Cognito user username: {email} and was not found'
            )


def delete_cognito_users(emails):
    for email in emails:
        logger.info(f'Delete cognito user username: {email}')
        try:
            cognito.admin_delete_user(UserPoolId=USER_POOL_ID, Username=email.lower())
        except cognito.exceptions.UserNotFoundException:
            logger.warning(
                f'Tried to delete Cognito user username: {email} and was not found'
            )


def remove_user_from_group(username, group_name):
    logger.info(
        f'Remove cognito user from group username: {username} group_name: {group_name}'
    )
    cognito.admin_remove_user_from_group(
        UserPoolId=USER_POOL_ID, Username=username.lower(), GroupName=group_name
    )


def update_user_group(username, group_name, updated_group_name):
    remove_user_from_group(username, group_name)
    add_user_to_group(username, updated_group_name)


def update_user_attributes(username, update_fields):
    params = {
        'UserAttributes': [
            {'Name': 'family_name', 'Value': update_fields.get('last_name')},
            {'Name': 'name', 'Value': update_fields.get('first_name')},
        ],
        'Username': username.lower(),
        'UserPoolId': USER_POOL_ID,
    }

    logger.info(
        f'Update cognito user attributes{exclude_dict_keys(params, ["UserPoolId"])}'
    )
    cognito.admin_update_user_attributes(**params)


def __load_cognito_keys():
    public_keys = {}
    url = (
        f'https://cognito-idp.{AWS_REGION}.amazonaws.com'
        f'/{USER_POOL_ID}/.well-known/jwks.json'
    )
    try:
        logger.info('Getting COGNITO Keys')
        jwks = requests.get(url, timeout=4).json()
        for jwk in jwks['keys']:
            kid = jwk['kid']
            public_keys[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
    except (JSONDecodeError, requests.ConnectTimeout, requests.ReadTimeout) as e:
        logger.exception(f'Error loading cognito keys {e}')
    return public_keys


COGNITO_KEYS = __load_cognito_keys()


def decode_token(token, verify=True, verify_exp=True, key=None):
    try:
        jwt.get_unverified_header(token)['kid']
    except Exception as e:
        logger.exception(f'Error getting cognito unverified headers: {e}')
        return None

    try:
        if not key and verify:
            key = COGNITO_KEYS[jwt.get_unverified_header(token)['kid']]
        cognito_token = jwt.decode(
            token,
            verify=verify,
            options={'verify_aud': False, 'verify_exp': verify_exp},
            key=key,
            algorithms=['RS256'],
        )

        cognito_token['username'] = cognito_token.get(COGNITO_USERNAME)
        cognito_token[AUTH_GROUPS] = cognito_token.get(COGNITO_GROUPS)
        cognito_token['idp'] = COGNITO

        return cognito_token
    except jwt.exceptions.ExpiredSignatureError as e:
        logger.exception(f'error trying to decode okta tokenvalidation failed: {e}')
        raise jwt.ExpiredSignatureError('Signature has expired')
    except KeyError:
        raise jwt.exceptions.InvalidKeyError('Token with unexpected key')


def associate_token(access_token):
    response = cognito.associate_software_token(AccessToken=access_token)
    secret_code = response.get('SecretCode')
    if not secret_code:
        raise ServiceException('Error MFA setup')
    return secret_code


def verify_token(access_token, code):
    return cognito.verify_software_token(AccessToken=access_token, UserCode=code)


def change_mfa_preference(user_name, value):
    cognito.admin_set_user_mfa_preference(
        SoftwareTokenMfaSettings={'Enabled': value, 'PreferredMfa': value},
        Username=user_name,
        UserPoolId=USER_POOL_ID,
    )

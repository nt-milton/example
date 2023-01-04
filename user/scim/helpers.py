import logging

from user.constants import OKTA_ROLES, ROLE_VIEWER
from user.models import User

logger = logging.getLogger('scim')


def generate_user_body(user):
    return {
        'schemas': ['urn:ietf:params:scim:schemas:core:2.0:User'],
        'id': user.id,
        'externalId': user.username,
        'meta': {
            'resourceType': 'User',
            'created': user.date_joined,
            'lastModified': user.updated_at,
        },
        'userName': f'{user.first_name} {user.last_name}',
        'name': {
            'formatted': f'{user.first_name} {user.last_name}',
            'familyName': user.last_name,
            'givenName': user.first_name,
        },
        'active': True,
        'emails': [{'value': user.email, 'type': 'work', 'primary': True}],
    }


def get_role_from_request(request_body, default_role=ROLE_VIEWER):
    for group in request_body.get('groups'):
        if group in OKTA_ROLES:
            return OKTA_ROLES[group]
    return default_role


def create_user_from_request(request_body, organization):
    role = get_role_from_request(request_body)
    return User(
        email=request_body['emails'][0]['value'],
        first_name=request_body['name']['givenName'],
        last_name=request_body['name']['familyName'],
        organization=organization,
        role=role,
        username=request_body['externalId'],
    )


def update_user_from_request(request_body, user):
    user.email = request_body['emails'][0]['value']
    user.first_name = request_body['name']['givenName']
    user.last_name = request_body['name']['familyName']
    user.username = request_body['externalId']
    return user


def patch_user_from_request(request_body, user):
    operation = request_body['operations'][0]
    if operation['op'] == 'replace' and 'active' in operation['value'].keys():
        if operation['value']['active']:
            user.deleted_at = None
        else:
            user.soft_delete_user()
        return user

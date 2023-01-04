from typing import Callable

from integration.jumpcloud.constants import (
    JUMPCLOUD,
    NOT_APPLICABLE,
    PRIVILEGED_ACCESSES,
)
from integration.models import ConnectionAccount
from objects.system_types import User


def _get_organizations_from_organization_options(
    connection_account: ConnectionAccount,
) -> dict:
    authentication = connection_account.authentication
    organization_options = authentication.get('prefetch_organization', [])
    organizations = [
        [organization['id'], organization['value']['name']]
        for organization in organization_options
    ]
    return dict(organizations)


def is_console_admin(user):
    return 'roleName' in user.keys()


def build_mapper_from_user_to_laika_object(
    connection_account: ConnectionAccount,
) -> Callable:
    organizations = _get_organizations_from_organization_options(connection_account)

    def map_function(user, connection_name):
        lo_user = User()
        lo_user.id = user['_id']
        lo_user.first_name = user['firstname']
        lo_user.last_name = user['lastname']
        lo_user.email = user['email']
        lo_user.title = NOT_APPLICABLE
        lo_user.organization_name = organizations[user['organization']]
        lo_user.groups = NOT_APPLICABLE
        lo_user.applications = NOT_APPLICABLE
        lo_user.mfa_enforced = NOT_APPLICABLE
        lo_user.source_system = JUMPCLOUD
        lo_user.connection_name = connection_name
        if is_console_admin(user):
            lo_user.is_admin = user['roleName'] in PRIVILEGED_ACCESSES
            lo_user.roles = user['roleName']
            lo_user.mfa_enabled = ['enableMultiFactor']
        else:
            lo_user.is_admin = user['sudo']
            lo_user.roles = NOT_APPLICABLE
            lo_user.mfa_enabled = user['mfa']['configured']
        return lo_user.data()

    return map_function

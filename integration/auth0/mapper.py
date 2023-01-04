from integration.auth0.implementation import AUTH0_SYSTEM
from integration.auth0.rest_client import get_user_organizations, get_user_roles
from objects.system_types import User


def map_user_builder(connection_account):
    def map_user_response_to_laika_object(response, connection_name):
        lo_user = User()
        lo_user.id = response.get('user_id')
        lo_user.first_name = response.get('given_name', response.get('name', ''))
        lo_user.last_name = response.get('family_name')
        lo_user.email = response.get('email')
        user_organizations = get_user_organizations(
            response.get('user_id'), connection_account
        )
        user_roles = get_user_roles(response.get('user_id'), connection_account)
        lo_user.organization_name = ', '.join(
            [item.get('display_name') for item in user_organizations]
        )
        lo_user.roles = ', '.join([item.get('name') for item in user_roles])
        lo_user.mfa_enabled = any(response.get('multifactor', []))
        lo_user.connection_name = connection_name
        lo_user.source_system = AUTH0_SYSTEM
        return lo_user.data()

    return map_user_response_to_laika_object

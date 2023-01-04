from integration.account import get_integration_laika_objects

AUTH0_SYSTEM = 'Auth0'
INSUFFICIENT_PERMISSIONS = '001'
N_RECORDS = get_integration_laika_objects(AUTH0_SYSTEM)
REQUIRED_SCOPES = (
    'read:users read:user_idp_tokens read:organizations read:roles read:role_members'
)

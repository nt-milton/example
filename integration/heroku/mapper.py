from collections import namedtuple

from objects.system_types import User

HEROKU_SYSTEM = 'Heroku'

HerokuRequest = namedtuple(
    'HerokuRequest',
    ('user', 'teams', 'roles'),
)


def _map_user_response_to_laika_object(response, connection_name):
    teams = response.teams
    roles = response.roles
    user = response.user
    user_object = user.get('user', {})
    lo_user = User()
    lo_user.id = user_object.get('id')
    lo_user.first_name = user_object.get('name')
    lo_user.last_name = ''
    lo_user.email = user_object.get('email')
    lo_user.title = ''
    lo_user.organization_name = ''
    lo_user.is_admin = 'admin' in roles
    lo_user.groups = ', '.join(sorted(teams))
    lo_user.applications = None
    lo_user.roles = ', '.join(sorted(roles))
    lo_user.connection_name = connection_name
    lo_user.mfa_enabled = user.get('two_factor_authentication')
    lo_user.mfa_enforced = ''
    lo_user.source_system = HEROKU_SYSTEM
    return lo_user.data()

from objects.system_types import User

SLACK_SYSTEM = 'Slack'


def map_users_to_laika_object(user, connection_name):
    lo_user = User()
    profile = user.get('profile', {})
    lo_user.id = user.get('id', None)
    lo_user.first_name = profile.get('first_name', '')
    lo_user.last_name = profile.get('last_name', '')
    lo_user.email = profile.get('email', '')
    lo_user.is_admin = user.get('is_admin', False)
    lo_user.title = profile.get('title', '')
    lo_user.organization_name = None
    lo_user.roles = ''
    lo_user.groups = ''
    lo_user.mfa_enabled = profile.get('has_2fa', False)
    lo_user.mfa_enforced = None
    lo_user.source_system = SLACK_SYSTEM
    lo_user.connection_name = connection_name
    if not lo_user.first_name and not lo_user.last_name and not lo_user.email:
        lo_user.first_name = user.get('real_name', '') or user.get('name', '')

    return lo_user.data()

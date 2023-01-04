from objects.system_types import User

AWS = 'Amazon Web Services (AWS)'


def map_user_to_laika_object(aws_user, connection_name):
    lo_user = User()
    lo_user.id = aws_user.user.get('UserId')
    lo_user.first_name = aws_user.user.get('UserName', '')
    lo_user.is_admin = aws_user.is_admin
    lo_user.organization_name = aws_user.organization.get('name', '')
    lo_user.email = ''
    lo_user.last_name = ''
    lo_user.title = ''
    lo_user.roles = ''
    lo_user.groups = aws_user.groups
    lo_user.mfa_enabled = aws_user.mfa
    lo_user.mfa_enforced = ''
    lo_user.source_system = AWS
    lo_user.connection_name = connection_name
    return lo_user.data()


def map_root_account_to_laika_object(aws_root_account, connection_name):
    lo_user = User()
    lo_user.id = aws_root_account.root_account.get('Id')
    lo_user.first_name = aws_root_account.root_account.get('Name', '')
    lo_user.is_admin = True
    lo_user.organization_name = aws_root_account.organization.get('name', '')
    lo_user.email = aws_root_account.root_account.get('Email', '')
    lo_user.last_name = ''
    lo_user.title = ''
    lo_user.roles = str(aws_root_account.roles)
    lo_user.groups = ''
    lo_user.mfa_enabled = ''
    lo_user.mfa_enforced = ''
    lo_user.connection_name = connection_name
    lo_user.source_system = AWS
    return lo_user.data()

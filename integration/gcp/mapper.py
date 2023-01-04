from typing import List

from integration.gcp.utils import GCP_ADMIN_ROLES
from objects.system_types import ServiceAccount, User


def map_gcp_project_members_response(member, connection_name, source_system):
    print('MEMBER', member)
    member_roles = member.get('roles')
    roles = get_mapped_roles(member_roles)
    is_admin = define_admin_by_roles(member_roles)
    lo_user = User()
    lo_user.id = member['id']
    lo_user.first_name = ''
    lo_user.last_name = ''
    lo_user.title = ''
    lo_user.email = member['email']
    lo_user.organization_name = ''
    lo_user.is_admin = is_admin
    lo_user.roles = ', '.join(sorted(roles))
    lo_user.groups = ''
    lo_user.mfa_enabled = ''
    lo_user.mfa_enforced = ''
    lo_user.source_system = source_system
    lo_user.connection_name = connection_name
    return lo_user.data()


def _get_split_member_values(split_member_values):
    action, member_type, email = None, None, None
    if len(split_member_values) == 2:
        member_type, email = split_member_values
    if len(split_member_values) == 3:
        action, member_type, email = split_member_values
    return action, member_type, email


def get_mapped_roles(roles: List) -> List:
    return [role.get('name') for role in roles]


def define_admin_by_roles(roles: List) -> bool:
    for role in roles:
        if role.get('name') in set(GCP_ADMIN_ROLES):
            return True

        if role.get('is_custom', False):
            is_admin_permissions = check_admin_permissions(role.get('permissions'))
            if is_admin_permissions:
                return True
    return False


def check_admin_permissions(permissions: List) -> bool:
    for permission in permissions:
        if '*' in permission.split('.')[-1]:
            return True

    return False


def map_gcp_project_service_accounts_response(
    service_account, connection_name, source_system
):
    lo_service_account = ServiceAccount()
    lo_service_account.id = service_account['uniqueId']
    lo_service_account.display_name = service_account.get('displayName', '')
    lo_service_account.description = (
        service_account['description'] if 'description' in service_account else ''
    )
    lo_service_account.owner_id = service_account['projectId']
    lo_service_account.email = service_account['email']
    lo_service_account.is_active = True if 'disabled' not in service_account else False
    lo_service_account.created_date = ''
    lo_service_account.roles = ', '.join(sorted(service_account.get('roles', [])))
    lo_service_account.source_system = source_system
    lo_service_account.connection_name = connection_name
    return lo_service_account.data()

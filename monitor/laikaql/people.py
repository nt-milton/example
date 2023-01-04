from organization.models import Organization


def build_query(organization: Organization) -> str:
    return f'''
    select
    u.id as people_id,
    u.username,
    u.first_name,
    u.last_name,
    u.email,
    u.is_active,
    u.date_joined,
    u.role,
    u.department,
    u.employment_status,
    u.employment_subtype,
    u.employment_type,
    u.end_date,
    u.phone_number,
    u.start_date,
    u.title,
    u.discovery_state,
    u.mfa,
    manager.email as manager
    from user_user as u
    left join user_user as manager on
    u.manager_id=manager.id
    where u.organization_id='{organization.id}'
    '''

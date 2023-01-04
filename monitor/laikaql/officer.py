from organization.models import Organization


def build_query(organization: Organization) -> str:
    return f'''
    select
    o.id as officer_id,
    o.created_at,
    o.updated_at,
    o.name as title,
    o.description,
    u.first_name,
    u.last_name
    from user_officer as o
    left join user_user as u on u.id = o.user_id
    where o.organization_id = '{organization.id}'
    '''

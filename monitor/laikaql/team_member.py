from organization.models import Organization


def build_query(organization: Organization) -> str:
    return f'''
    select
    tm.id as team_member_id,
    tm.created_at,
    tm.updated_at,
    t.name as team_name,
    u.first_name,
    u.last_name,
    tm.role,
    tm.phone,
    u.email
    from user_teammember as tm
    left join user_team as t on t.id = tm.team_id
    left join user_user as u on u.id = tm.user_id
    where u.organization_id = '{organization.id}'
    '''

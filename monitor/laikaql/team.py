from organization.models import Organization


def build_query(organization: Organization) -> str:
    return f'''
    select
    id as team_id,
    created_at,
    updated_at,
    name,
    description,
    charter,
    notes
    from user_team
    where organization_id = '{organization.id}'
    '''

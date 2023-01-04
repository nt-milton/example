from organization.models import Organization


def build_query(organization: Organization) -> str:
    return f'''
    select tt.id as training_id, tt.created_at,
    tt.updated_at, tt.name,
    tt.category, tt.description,
    tt.slides as file_name , tt.roles,
    CASE WHEN EXISTS(
    SELECT ta.training_id
    FROM training_alumni ta
    WHERE
    tt.id = ta.training_id)
    THEN 'COMPLETED'
    ELSE 'NOT STARTED'
    END AS state
    from training_training tt
    where tt.organization_id = '{organization.id}'
    '''

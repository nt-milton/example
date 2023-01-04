from organization.models import Organization


def build_query(organization: Organization) -> str:
    return f'''
    select
    ta.id as training_alumni_id,
    ta.created_at,
    ta.training_id,
    ta.email, ta.first_name,
    ta.last_name, ta.training_category,
    ta.training_name
    from training_alumni ta
    left join training_training tt on tt.id = ta.training_id
    where tt.organization_id = '{organization.id}'
    '''

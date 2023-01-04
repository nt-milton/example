from organization.models import Organization


def build_query(organization: Organization) -> str:
    return f'''
    select
    t.id as task_id,
    t.created_at,
    t.updated_at,
    t.name,
    p.name as program,
    t.description,
    t.category,
    t.how_to_guide,
    t.implementation_notes,
    t.tier,
    t.overview,
    t.customer_identifier,
    t.number
    from
    program_task as t
    left join program_program as p
    on p.id = t.program_id
    where p.organization_id = '{organization.id}'
    '''

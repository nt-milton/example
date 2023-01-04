from organization.models import Organization


def build_query(organization: Organization) -> str:
    return f'''
    select
    v.id as action_item_id,
    v.created_at,
    v.updated_at,
    v.due_date,
    v.completed_on,
    v.status,
    v.type,
    v.description,
    v.group,
    u.first_name || ' ' || u.last_name as assignee
    from dashboard_view as v
    left join user_user as u
    on u.id = v.assignee_id
    where v.organization_id = '{organization.id}'
    '''

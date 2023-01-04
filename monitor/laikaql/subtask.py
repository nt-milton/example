from organization.models import Organization


def build_query(organization: Organization) -> str:
    return f'''
    select
    st.id as subtask_id,
    st.created_at,
    st.updated_at,
    t.name as task,
    p.name as program,
    a.first_name || ' ' || a.last_name as assignee,
    st.text,
    st.group,
    st.requires_evidence,
    st.sort_index,
    st.due_date,
    st.priority,
    st.status,
    st.badges,
    st.is_system_subtask,
    st.complexity,
    st.complexity_group,
    st.completed_on,
    st.customer_identifier,
    st.number
    from
    program_subtask as st
    left join program_task as t
    on st.task_id = t.id
    left join program_program as p
    on t.program_id = p.id
    left join user_user as a
    on st.assignee_id = a.id
    where p.organization_id = '{organization.id}'
    '''

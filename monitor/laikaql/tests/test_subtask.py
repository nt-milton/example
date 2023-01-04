import pytest
from django.db import connection

from monitor.laikaql.subtask import build_query
from organization.tests import create_organization


@pytest.mark.functional
def test_get_query_builder_by_alias_for_subtask():
    organization = create_organization(name='Test')
    policy_query = build_query(organization)
    expected_query = f'''
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
    assert expected_query == policy_query


@pytest.mark.functional
def test_database_consistency_for_subtasks():
    with connection.cursor() as cursor:
        queries = [
            '''
            select created_at, updated_at, text, "group", requires_evidence,
            sort_index, due_date, priority, status, badges, is_system_subtask,
            complexity, complexity_group, completed_on, customer_identifier,
            number, task_id, assignee_id from program_subtask
            ''',
            'select id, name, program_id from program_task',
            'select id, name, organization_id from program_program',
            'select id, first_name, last_name from user_user',
        ]
        for query in queries:
            cursor.execute(query)

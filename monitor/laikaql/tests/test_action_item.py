import pytest
from django.db import connection

from monitor.laikaql.action_item import build_query
from organization.tests import create_organization


@pytest.mark.functional
def test_get_query_builder_by_alias_for_action_item():
    organization = create_organization(name='Test')
    control_query = build_query(organization)
    expected_query = f'''
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
    assert expected_query == control_query


@pytest.mark.functional
def test_database_consistency_for_action_items():
    with connection.cursor() as cursor:
        queries = [
            '''
            select created_at, updated_at, due_date, completed_on, status,
            type, description, "group", assignee_id,
            organization_id from dashboard_view
            ''',
            'select id, first_name, last_name from user_user',
        ]
        for query in queries:
            cursor.execute(query)

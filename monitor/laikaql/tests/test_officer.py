import pytest
from django.db import connection

from monitor.laikaql.officer import build_query
from organization.tests import create_organization


@pytest.mark.functional
def test_get_query_builder_by_alias_for_officer():
    organization = create_organization(name='Test')
    monitor_query = build_query(organization)
    expected_query = f'''
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
    assert expected_query == monitor_query


@pytest.mark.functional
def test_database_consistency_for_officer():
    with connection.cursor() as cursor:
        queries = [
            '''
            select created_at, updated_at, name, description, user_id, id,
            organization_id from user_officer
            ''',
            'select first_name, last_name from user_user',
        ]
        for query in queries:
            cursor.execute(query)

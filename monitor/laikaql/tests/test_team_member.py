import pytest
from django.db import connection

from monitor.laikaql.team_member import build_query
from organization.tests import create_organization


@pytest.mark.functional
def test_get_query_builder_by_alias_for_team_members():
    organization = create_organization(name='Test')
    monitor_query = build_query(organization)
    expected_query = f'''
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
    assert expected_query == monitor_query


@pytest.mark.functional
def test_database_consistency_for_team_members():
    with connection.cursor() as cursor:
        queries = [
            '''
            select id, name as team_name from user_team
            ''',
            '''
            select created_at, phone, role, team_id, updated_at, user_id
            from user_teammember
            ''',
            '''
            select email, first_name, id, last_name, organization_id
            from user_user
            ''',
        ]
        for query in queries:
            cursor.execute(query)

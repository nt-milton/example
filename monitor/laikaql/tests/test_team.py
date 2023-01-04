import pytest
from django.db import connection

from monitor.laikaql.team import build_query
from organization.tests import create_organization


@pytest.mark.functional
def test_get_query_builder_for_teams():
    organization = create_organization(name='Test')
    monitor_query = build_query(organization)
    expected_query = f'''
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
    assert expected_query == monitor_query


@pytest.mark.functional
def test_database_consistency_for_teams():
    with connection.cursor() as cursor:
        query = '''
        select created_at, updated_at, name, description, charter, notes,
        organization_id from user_team
        '''
        cursor.execute(query)

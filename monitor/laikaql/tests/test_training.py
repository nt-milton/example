import pytest
from django.db import connection

from monitor.laikaql.training import build_query
from organization.tests import create_organization


@pytest.mark.functional
def test_get_query_builder_by_alias_for_training():
    organization = create_organization(name='Test')
    monitor_query = build_query(organization)
    expected_query = f'''
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
    assert expected_query == monitor_query


@pytest.mark.functional
def test_database_consistency_for__training():
    with connection.cursor() as cursor:
        queries = [
            '''
            select id, created_at,
            updated_at, name,
            category, description,
            slides, roles
            from training_training
            ''',
            '''
           select training_id
           from training_alumni
           ''',
        ]
        for query in queries:
            cursor.execute(query)

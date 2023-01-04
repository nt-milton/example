import pytest
from django.db import connection

from monitor.laikaql.training_alumni import build_query
from organization.tests import create_organization


@pytest.mark.functional
def test_get_query_builder_by_alias_for_training_alumni():
    organization = create_organization(name='Test')
    monitor_query = build_query(organization)
    expected_query = f'''
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
    assert expected_query == monitor_query


@pytest.mark.functional
def test_database_consistency_for__training_alumni():
    with connection.cursor() as cursor:
        queries = [
            '''
            select created_at,
            training_id,
            email, first_name,
            last_name, training_category,
            training_name
            from training_alumni
            ''',
            '''
            select id, organization_id
            from training_training
            ''',
        ]
        for query in queries:
            cursor.execute(query)

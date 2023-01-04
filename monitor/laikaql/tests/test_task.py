import pytest
from django.db import connection

from monitor.laikaql.task import build_query
from organization.tests import create_organization


@pytest.mark.functional
def test_get_query_builder_by_alias_for_task():
    organization = create_organization(name='Test')
    policy_query = build_query(organization)
    expected_query = f'''
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
    assert expected_query == policy_query


@pytest.mark.functional
def test_database_consistency_for_tasks():
    with connection.cursor() as cursor:
        queries = [
            '''
            select created_at, updated_at, name, description, category,
            how_to_guide, implementation_notes, tier, overview,
            customer_identifier, number, program_id from program_task
            ''',
            'select id, name, organization_id from program_program',
        ]
        for query in queries:
            cursor.execute(query)

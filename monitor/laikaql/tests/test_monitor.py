import pytest
from django.db import connection

from monitor.laikaql.monitor import build_query
from organization.tests import create_organization


@pytest.mark.functional
def test_get_query_builder_by_alias_for_monitors():
    organization = create_organization(name='Test')
    monitor_query = build_query(organization)
    expected_query = f'''
    select
    om.id as monitor_instance_id,
    m.id as monitor_id,
    m.name as name,
    m.description as description,
    m.query as query,
    m.health_condition as health_condition,
    m.monitor_type as monitor_type,
    m.frequency as frequency,
    om.active as active,
    om.status as status,
    mr.created_at as last_run,
    string_to_array(
        regexp_replace(
            m.tag_references, E'[\\n\\r]+', ',', 'g'
        ),
        ','
    ) as tags,
    string_to_array(
        regexp_replace(
            m.control_references, E'[\\n\\r]+', ',', 'g'
        ),
        ','
    ) as controls
    from monitor_organizationmonitor as om
    left join monitor_monitor as m
    on m.id = om.monitor_id
    left join monitor_monitorresult as mr
    on mr.created_at = (
        select max(mr.created_at)
        from monitor_monitorresult as mr
        where mr.organization_monitor_id = om.id
    )
    where om.organization_id = '{organization.id}'
    '''
    assert expected_query == monitor_query


@pytest.mark.functional
def test_database_consistency_for_monitors():
    with connection.cursor() as cursor:
        queries = [
            '''
            select id, name, description, query, health_condition,
            monitor_type, frequency, tag_references, control_references
            from monitor_monitor
            ''',
            '''
            select id, active, status, monitor_id, organization_id
            from monitor_organizationmonitor
            ''',
            '''
            select created_at, organization_monitor_id
            from monitor_monitorresult
            ''',
        ]
        for query in queries:
            cursor.execute(query)

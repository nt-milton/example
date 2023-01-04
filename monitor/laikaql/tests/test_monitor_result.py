import json

import pytest
from django.db import connection

from monitor.laikaql.monitor_result import (
    LIMIT_RESULT_MESSAGE,
    LIMIT_RESULT_SIZE,
    build_query,
)
from monitor.tests.factory import create_monitor_result
from organization.tests import create_organization


@pytest.mark.functional
def test_get_query_builder_by_alias_for_monitor_results():
    organization = create_organization(name='Test')
    monitor_result_query = build_query(organization)
    expected_query = f'''
    select
    mr.id as monitor_result_id,
    mr.created_at,
    mr.query,
    mr.status,
    CASE
        WHEN LENGTH(CAST(mr.result AS TEXT)) > {LIMIT_RESULT_SIZE}
            THEN '{LIMIT_RESULT_MESSAGE}'
        ELSE CAST(mr.result AS TEXT)
    END as result,
    m.name as monitor
    from monitor_monitorresult as mr
    left join monitor_organizationmonitor as om
    on om.id = mr.organization_monitor_id
    left join monitor_monitor as m
    on m.id = om.monitor_id
    where om.organization_id='{organization.id}'
    '''
    assert expected_query == monitor_result_query


@pytest.mark.functional
def test_database_consistency_for_monitor_results():
    with connection.cursor() as cursor:
        queries = [
            '''
            select created_at, query, status, result, organization_monitor_id
            from monitor_monitorresult
            ''',
            'select id, name from monitor_monitor',
            '''
            select id, monitor_id, organization_id from
            monitor_organizationmonitor
            ''',
        ]
        for query in queries:
            cursor.execute(query)


@pytest.mark.functional
def test_response_for_large_result():
    monitor_result = create_monitor_result(
        result={
            'columns': ['text'],
            'data': [['.' * LIMIT_RESULT_SIZE]],
        }
    )
    organization = monitor_result.organization_monitor.organization
    monitor_result_query = build_query(organization).replace(
        str(organization.id), str(organization.id).replace('-', '')
    )
    with connection.cursor() as cursor:
        cursor.execute(monitor_result_query)
        columns = [col[0] for col in cursor.description]
        result = cursor.fetchall()
        assert result[0][columns.index('result')] == LIMIT_RESULT_MESSAGE


@pytest.mark.functional
def test_response_for_short_result():
    monitor_result = create_monitor_result(
        result={
            'columns': [],
            'data': [],
        }
    )
    organization = monitor_result.organization_monitor.organization
    monitor_result_query = build_query(organization).replace(
        str(organization.id), str(organization.id).replace('-', '')
    )
    with connection.cursor() as cursor:
        cursor.execute(monitor_result_query)
        columns = [col[0] for col in cursor.description]
        result = cursor.fetchall()
        assert result[0][columns.index('result')] == json.dumps(monitor_result.result)

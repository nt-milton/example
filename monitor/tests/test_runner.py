import pytest
from django.db import DatabaseError

from monitor.models import MonitorHealthCondition, MonitorInstanceStatus
from monitor.result import AggregateResult
from monitor.result import Result as SingleResult
from monitor.runner import (
    INCORRECT_QUERIES_NUMBER_ERROR,
    INCORRECT_QUERY_OPERATION_ERROR,
    RESULT_SIZE_LIMIT,
    _validate_query,
    _validate_result,
)

EXCEPTION_MONITOR = MonitorHealthCondition.EMPTY_RESULTS
EVIDENCE_MONITOR = MonitorHealthCondition.RETURN_RESULTS
COLUMN_NAMES = ['column 1', 'column 2']
RESULT_DATA = [['data 1', 'data 2']]
RESULT = SingleResult(columns=COLUMN_NAMES, data=RESULT_DATA)
EMPTY_RESULT = SingleResult(columns=COLUMN_NAMES, data=[])
NO_DATASOURCE_RESULT = SingleResult(columns=[], data=[])

QUERIES_DATA = [
    (
        'select * from aws_iam_user; drop table aws_iam_user;',
        INCORRECT_QUERIES_NUMBER_ERROR,
    ),
    ('drop * from aws_iam_user;', f'DROP {INCORRECT_QUERY_OPERATION_ERROR}'),
    ('create table aws_iam_user;', f'CREATE {INCORRECT_QUERY_OPERATION_ERROR}'),
    ('delete * from aws_iam_user;', f'DELETE {INCORRECT_QUERY_OPERATION_ERROR}'),
    (
        'insert into policy_policy ('
        '"", "", 1, "", "name", "description" ,None, None, None,'
        'None, None, None, None, None, None,""'
        ');',
        f'INSERT {INCORRECT_QUERY_OPERATION_ERROR}',
    ),
    ('select * from user_user', 'table "user_user" does not exist'),
    ('select select name from tag_tag from lo_users', 'table "tag_tag" does not exist'),
    (
        'select (select name from policy_policy) from lo_users',
        'table "policy_policy" does not exist',
    ),
]


def test_empty_result_triggered():
    status = EMPTY_RESULT.status(EVIDENCE_MONITOR)
    assert status == MonitorInstanceStatus.TRIGGERED


def test_result_healthy():
    status = RESULT.status(EVIDENCE_MONITOR)
    assert status == MonitorInstanceStatus.HEALTHY


def test_empty_result_healthy():
    status = EMPTY_RESULT.status(EXCEPTION_MONITOR)
    assert status == MonitorInstanceStatus.HEALTHY


def test_result_triggered():
    status = RESULT.status(EXCEPTION_MONITOR)
    assert status == MonitorInstanceStatus.TRIGGERED


@pytest.mark.parametrize(
    'results, expected_result',
    [
        ([RESULT], SingleResult(columns=COLUMN_NAMES, data=RESULT_DATA)),
        ([EMPTY_RESULT], SingleResult(columns=COLUMN_NAMES, data=[])),
        (
            [EMPTY_RESULT, RESULT],
            SingleResult(columns=COLUMN_NAMES, data=RESULT_DATA),
        ),
        (
            [EMPTY_RESULT, RESULT, NO_DATASOURCE_RESULT],
            SingleResult(columns=COLUMN_NAMES, data=RESULT_DATA),
        ),
        (
            [RESULT] * 2,
            SingleResult(columns=COLUMN_NAMES, data=RESULT_DATA + RESULT_DATA),
        ),
        ([EMPTY_RESULT] * 2, SingleResult(columns=COLUMN_NAMES, data=[])),
        (
            [RESULT, RESULT, NO_DATASOURCE_RESULT],
            SingleResult(columns=COLUMN_NAMES, data=RESULT_DATA * 2),
        ),
        (
            [EMPTY_RESULT, EMPTY_RESULT, NO_DATASOURCE_RESULT],
            SingleResult(columns=COLUMN_NAMES, data=[]),
        ),
        (
            [NO_DATASOURCE_RESULT],
            SingleResult(columns=[], data=[]),
        ),
        (
            [],
            SingleResult(columns=[], data=[]),
        ),
    ],
)
def test_result_aggregation_structure(results, expected_result):
    aggregate_result = AggregateResult(results)
    json = aggregate_result.to_json()
    expected_json = expected_result.to_json()
    assert json == expected_json


@pytest.mark.parametrize(
    'results, health_condition',
    [
        ([RESULT], EXCEPTION_MONITOR),
        ([EMPTY_RESULT], EVIDENCE_MONITOR),
        ([EMPTY_RESULT, RESULT], EXCEPTION_MONITOR),
        ([EMPTY_RESULT, RESULT], EVIDENCE_MONITOR),
        ([EMPTY_RESULT, RESULT, NO_DATASOURCE_RESULT], EXCEPTION_MONITOR),
        ([EMPTY_RESULT, RESULT, NO_DATASOURCE_RESULT], EVIDENCE_MONITOR),
    ],
)
def test_triggered_aggregates(results, health_condition):
    status = AggregateResult(results).status(health_condition)
    assert status == MonitorInstanceStatus.TRIGGERED


@pytest.mark.parametrize(
    'results, health_condition',
    [
        ([RESULT], EVIDENCE_MONITOR),
        ([EMPTY_RESULT], EXCEPTION_MONITOR),
        ([RESULT, RESULT], EVIDENCE_MONITOR),
        ([EMPTY_RESULT, EMPTY_RESULT], EXCEPTION_MONITOR),
        ([RESULT, NO_DATASOURCE_RESULT], EVIDENCE_MONITOR),
        ([EMPTY_RESULT, NO_DATASOURCE_RESULT], EXCEPTION_MONITOR),
    ],
)
def test_healthy_aggregates(results, health_condition):
    status = AggregateResult(results).status(health_condition)
    assert status == MonitorInstanceStatus.HEALTHY


@pytest.mark.parametrize(
    'results, health_condition',
    [
        ([NO_DATASOURCE_RESULT], EXCEPTION_MONITOR),
        ([NO_DATASOURCE_RESULT], EVIDENCE_MONITOR),
        ([], EXCEPTION_MONITOR),
        ([], EVIDENCE_MONITOR),
    ],
)
def test_no_datasource_aggregation(
    results,
    health_condition,
):
    status = AggregateResult(results).status(health_condition)
    assert status == MonitorInstanceStatus.CONNECTION_ERROR


@pytest.mark.parametrize('query, message', QUERIES_DATA)
def test_validate_query_error_case(query, message):
    with pytest.raises(DatabaseError) as err:
        _validate_query(query)
    assert str(err.value) == message


def test_validate_query_without_error():
    query = 'select * from aws_iam_user;'
    _validate_query(query)


def test_validate_query_with_empty_line():
    query = 'select * from policies where \'Access\'=ANY(tags);\n'
    _validate_query(query)


def test_validate_json_function_no_exceptions():
    query = '''
    select name, acc -> 'scopes' as scopes
    from gcp_compute_instance gci, jsonb_array_elements(service_accounts) acc,
    jsonb_array_elements_text(service_accounts) acc2
    where acc -> 'scopes' ? 'https://www.googleapis.com'
    '''
    _validate_query(query)


def test_validate_result_size():
    with pytest.raises(DatabaseError) as err:
        _validate_result(
            SingleResult(
                columns=['column1'],
                data=[['1' * RESULT_SIZE_LIMIT]],
            )
        )
    assert str(err.value) == 'Result is too large.'

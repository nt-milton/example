import logging
import timeit
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable

from django.db import DatabaseError, connection, utils
from sqlparse import parse
from sqlparse.sql import Parenthesis, Statement

from integration.exceptions import ConfigurationError
from monitor import exclusion, factory, template
from monitor.action_item import reconcile_action_items
from monitor.laikaql import LAIKA_TABLES, build_raw_query
from monitor.models import (
    MonitorExclusion,
    MonitorInstanceStatus,
    MonitorResult,
    OrganizationMonitor,
)
from monitor.result import Result
from monitor.sqlutils import (
    _get_table_names,
    add_limit_clause,
    delete_where_clause,
    is_cloud_table,
)
from objects.models import LaikaObjectType
from organization.models import Organization
from user.models import User

RESULT_SIZE_LIMIT = 2 * 1024 * 1024

logger = logging.getLogger(__name__)
NO_DATASOURCE_RESULT = Result(columns=[], data=[])
INCORRECT_QUERIES_NUMBER_ERROR = '2 or more queries are not allowed.'
INCORRECT_QUERY_OPERATION_ERROR = (
    'is not allowed. Monitors support read-only operations.'
)
SAFE_FUNCTIONS = ['jsonb_array_elements', 'jsonb_array_elements_text']


executor = ThreadPoolExecutor(max_workers=5)


def asyn_run(organization_monitor: OrganizationMonitor, user: User = None):
    asyn_task(run, organization_monitor, user)


def asyn_task(task: Callable, *args):
    def validate_closed():
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_backend_pid();')
        except (utils.InterfaceError, utils.OperationalError) as exc:
            messages = ['server closed the connection', 'connection already closed']
            closed = any([message in str(exc) for message in messages])
            if closed:
                logger.info('Closed connection detection reconnect...')
                connection.connect()
        task(*args)

    def done(future: Future):
        if future.exception():
            logger.error(f'Error {future.exception()}')

    future = executor.submit(validate_closed)
    future.add_done_callback(done)


def log_organization_monitor_error(
    organization_monitor: OrganizationMonitor, exception: str
):
    logger.warning(
        f'Error with organization monitor {organization_monitor}. Error: {exception}'
    )


def validate_dependencies(organization: Organization, validation_query: str) -> bool:
    if not validation_query:
        return True
    query = build_raw_query(organization, validation_query)
    with connection.cursor() as cursor:
        cursor.execute(query)
        return len(cursor.fetchall()) > 0


def run(organization_monitor: OrganizationMonitor, user: User = None):
    organization = organization_monitor.organization
    monitor = organization_monitor.monitor
    logger.info(f'Running {monitor.name} org monitor id: {organization_monitor.id}')
    query = template.build_query_for_variables(
        organization_monitor.query or monitor.query,
        monitor.fix_me_link,
        monitor.exclude_field,
    )
    start_time = timeit.default_timer()
    result = dry_run(organization, query, monitor.validation_query, monitor.runner_type)
    execution_time = timeit.default_timer() - start_time
    result = exclude_results(
        organization_monitor, template.extract_placeholders(result)
    )
    save_result(organization_monitor, result, execution_time, user)


def exclude_results(
    organization_monitor: OrganizationMonitor, result: Result
) -> Result:
    if result.error:
        return result
    exclusion_criteria = MonitorExclusion.objects.filter(
        organization_monitor=organization_monitor, is_active=True
    )
    exclude_result = exclusion.exclude_result(result, exclusion_criteria)
    exclusion.exclusion_events(exclude_result, exclusion_criteria)
    return exclude_result


def get_column_key(key):
    return key.split('.')[1]


def save_result(
    organization_monitor: OrganizationMonitor,
    result: Result,
    execution_time: float = 0,
    user: User = None,
):
    from monitor.events import _has_unfiltered_data

    monitor = organization_monitor.monitor
    status = result.status(monitor.health_condition)
    if status != MonitorInstanceStatus.CONNECTION_ERROR and not _has_unfiltered_data(
        organization_monitor
    ):
        status = MonitorInstanceStatus.NO_DATA_DETECTED
    MonitorResult.objects.create(
        organization_monitor=organization_monitor,
        result=result.to_json(),
        status=status,
        query=organization_monitor.query or monitor.query,
        health_condition=monitor.health_condition,
        execution_time=execution_time,
        user=user,
    )
    organization_monitor.status = status
    organization_monitor.save()
    reconcile_action_items(organization_monitor)


def dry_run(
    organization: Organization,
    query: str,
    validation_query: str,
    runner_type: str,
) -> Result:
    result = NO_DATASOURCE_RESULT
    try:
        _validate_query(query)
        if validate_dependencies(organization, validation_query):
            context = factory.get_monitor_runner(runner_type)
            result = context.run(organization, query)
            _validate_result(result)
    except (
        DatabaseError,
        ConfigurationError,
        LaikaObjectType.DoesNotExist,
    ) as exception:
        result = Result.from_error(str(exception))
    return result


def _validate_query(query: str):
    parsed_queries = parse(query.strip())
    _one_query(parsed_queries)
    _select_query(parsed_queries[0])
    _validate_table_names(query)


def _validate_table_names(query: str):
    tables = _get_table_names(query)
    parsed_queries = parse(query)
    for table in tables:
        if (
            table not in LAIKA_TABLES
            and not is_cloud_table(table)
            and table not in SAFE_FUNCTIONS
        ):
            raise DatabaseError(f'table "{table}" does not exist')
    _validate_nested_query(parsed_queries[0])


def _validate_nested_query(parsed_query: Statement):
    for tokens in parsed_query:
        if isinstance(tokens, Parenthesis):
            _validate_table_names(tokens.value[1:-1])


def _one_query(parsed_queries: list[Statement]):
    if len(parsed_queries) > 1:
        raise DatabaseError(INCORRECT_QUERIES_NUMBER_ERROR)


def _select_query(parsed_query: Statement):
    query_type = parsed_query.get_type()
    if not query_type == 'SELECT':
        raise DatabaseError(f'{query_type} {INCORRECT_QUERY_OPERATION_ERROR}')


def build_unfiltered_query(query: str, limit: int) -> str:
    return add_limit_clause(delete_where_clause(query.replace(';', '')), limit)


def _validate_result(result: Result):
    data_size = len(str(result.data))
    if data_size > RESULT_SIZE_LIMIT:
        logger.error(f'Monitor result too large, data size: {data_size}')
        raise DatabaseError('Result is too large.')

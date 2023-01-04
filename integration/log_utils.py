import dataclasses
import logging
import timeit
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import Optional, Union

from integration.models import ConnectionAccount


@dataclasses.dataclass
class IntegrationContex:
    connection: ConnectionAccount
    retries: int = 0
    network_calls: int = 0
    network_wait: float = 0.0
    start_time: float = 0.0
    custom_metric: dict = dataclasses.field(default_factory=dict)
    object_cache: dict = dataclasses.field(default_factory=dict)


connection_context: ContextVar[Optional[IntegrationContex]] = ContextVar(
    "connection", default=None
)


# The function passed to the "after" param on the @retry method
# should receive this single param called retry_state
def increment_retry(retry_state) -> None:
    context = connection_context.get()
    if context:
        context.retries += 1


@contextmanager
def network_wait():
    context = connection_context.get()
    start_time = timeit.default_timer()
    try:
        yield
    finally:
        if context:
            context.network_calls += 1
            context.network_wait += timeit.default_timer() - start_time


@contextmanager
def time_metric(metric_name: str):
    context = connection_context.get()
    start_time = timeit.default_timer()
    try:
        yield
    finally:
        if context:
            current_val = context.custom_metric.get(metric_name, 0.0)
            context.custom_metric[metric_name] = current_val + (
                timeit.default_timer() - start_time
            )


@contextmanager
def connection_log(connection: ConnectionAccount):
    contex = IntegrationContex(connection, start_time=timeit.default_timer())
    prev = connection_context.set(contex)
    try:
        yield
    finally:
        connection_context.reset(prev)


def log_request(
    url: str = '',
    function: str = '',
    logger_name: str = __name__,
    finch_request_id=None,
    **kwargs,
) -> None:
    custom_logger = logging.getLogger(logger_name)
    message = f'URL: {url} - Function {function}'
    connection_id = _get_connection_account_id(**kwargs)
    if connection_id:
        message = f'Connection account {connection_id} - {message}'
    if finch_request_id:
        message = (
            f'Connection account {connection_id} - Finch-Request-Id: {finch_request_id}'
        )
    custom_logger.info(message)


def log_request_action(
    vendor: str,
    action: str,
    is_started: bool = True,
    logger_name: str = __name__,
    connection_id: str = None,
    is_generator: bool = False,
) -> None:
    if is_generator and not is_started:
        return

    def _get_status_log():
        return 'Started' if is_started else 'Ended'

    custom_logger = logging.getLogger(logger_name)
    message = f'{vendor} - Processing {action} - {_get_status_log()}'
    if connection_id:
        message = f'Connection account {connection_id} - {message}'
    custom_logger.info(message)


def log_action(
    vendor_name: str, logger_name: str = __name__, is_generator: bool = False
):
    def perform_logging(function):
        def _log(connection_id: str = None, is_started: bool = True):
            log_request_action(
                vendor_name,
                function.__name__,
                is_started,
                logger_name,
                connection_id,
                is_generator,
            )

        @wraps(function)
        def decorator(*args, **kwargs):
            connection_id = _get_connection_account_id(*args, **kwargs)

            _log(connection_id)
            result = function(*args, **kwargs)
            _log(connection_id, False)

            return result

        return decorator

    return perform_logging


def _get_connection_account_id(*args, **kwargs) -> Union[str, None]:
    if not kwargs and not args and not connection_context.get():
        return None
    context = connection_context.get()
    connection_account = (
        context.connection if context else kwargs.get('connection_account')
    )
    if connection_account:
        return str(connection_account.id)

    for value in args:
        if isinstance(value, ConnectionAccount):
            return str(value.id)

    return None


def connection_data(
    connection_account: Optional[ConnectionAccount],
) -> dict[str, ConnectionAccount]:
    if not connection_account:
        return {}
    return {'connection_account': connection_account}


def logger_extra(message: Union[str, None] = None, **kwargs):
    extra = {}
    if not message:
        message = ''
    connection_id = _get_connection_account_id(**kwargs)
    if connection_id:
        extra['Connection account'] = connection_id

    for key in extra:
        message = f'{key} {extra[key]} - {message}'

    return message

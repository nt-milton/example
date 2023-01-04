import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any, List, Union

import boto3
import requests
import urllib3.response as urllib3_response
from botocore.exceptions import ClientError
from dateutil.relativedelta import relativedelta

from integration import factory
from integration.alerts import search_error_message_by_regex_result
from integration.constants import OPTIMIZED_INTEGRATIONS
from integration.error_codes import USER_INPUT_ERROR
from integration.exceptions import ConfigurationError, TimeoutException
from integration.log_utils import logger_extra
from integration.models import (
    ConnectionAccount,
    ErrorCatalogue,
    Integration,
    IntegrationAlert,
)
from laika.aws.secrets import REGION_NAME
from laika.celery import LONG_RUN_QUEUE
from laika.celery import app as celery_app
from laika.constants import SECONDS_IN_DAY, SECONDS_IN_MINUTE
from objects.system_types import resolve_laika_object_type
from organization.models import Organization

PREFETCH = 'prefetch_'
THREE_SEMESTERS = 18
ONE_DAY = 1

logger = logging.getLogger(__name__)


def prefetch(connection_account, field, options=None):
    metadata = connection_account.integration.metadata
    if 'configuration_fields' not in metadata:
        return

    if not options:
        integration = factory.get_integration(connection_account)
        options = integration.get_custom_field_options(
            field, connection_account
        ).options

    connection_account.set_prefetched_options(field=field, options=options)


def get_first_last_name(fullname):
    first_name, *last_name = fullname.split(' ', maxsplit=1)
    return first_name, last_name[0] if last_name else ''


def get_last_run(connection_account: ConnectionAccount) -> Union[str, None]:
    last_run = connection_account.configuration_state.get('last_successful_run')
    if last_run:
        last_run = datetime.fromtimestamp(last_run)
        return last_run.strftime('%Y-%m-%d')

    return None


def calculate_date_range():
    now = datetime.now()
    finish_date = now - relativedelta(months=THREE_SEMESTERS)
    return finish_date.strftime("%Y-%m-%d")


def resolve_laika_object_types(
    organization: Organization, laika_object_types: List
) -> List:
    return [
        resolve_laika_object_type(organization, laika_object)
        for laika_object in laika_object_types
    ]


def validate_graphql_connection_error(response, data):
    if response.status_code != HTTPStatus.OK or data.get('errors'):
        raise ConnectionError(f'Linear error {response.status_code} {data}')


def wait_if_rate_time_api(response: Any, **kwargs) -> None:
    is_request_response = isinstance(response, requests.Response)
    is_urllib_response = isinstance(response, urllib3_response.HTTPResponse)
    if 'Retry-After' in response.headers:
        logger.info(logger_extra(f'Response headers: {response.headers}', **kwargs))
    retry_after_time = response.headers.get('Retry-After', 60)

    def _get_sleep_time():
        return int(retry_after_time)

    def _sleep():
        time.sleep(_get_sleep_time())

    def _log_waiting_time():
        logger.info(
            logger_extra(
                f'Reached rate limit, waiting {_get_sleep_time()} seconds', **kwargs
            )
        )

    if (
        is_request_response
        and int(response.status_code) == HTTPStatus.TOO_MANY_REQUESTS
    ):
        _log_waiting_time()
        _sleep()

    if is_urllib_response and int(response.status) == HTTPStatus.TOO_MANY_REQUESTS:
        _log_waiting_time()
        _sleep()


def normalize_integration_name(vendor_name: str) -> str:
    return vendor_name.replace(' ', '_').lower()


def wizard_error(
    connection_account: ConnectionAccount, wizard_error_code: str = ''
) -> ConfigurationError:
    vendor = connection_account.integration.vendor.name
    alert = IntegrationAlert.objects.filter(
        integration__vendor__name=vendor, wizard_error_code=wizard_error_code
    ).first()
    if not alert:
        catalogue_error = ErrorCatalogue.objects.get(code=USER_INPUT_ERROR)
        return _configuration_error(
            error_message=catalogue_error.default_wizard_message
        )
    return _configuration_error(
        error_message=alert.wizard_message if alert else '', error_code=alert.error.code
    )


def _get_wizard_error_message(connection_account, error) -> str:
    alerts_with_regex = connection_account.integration.get_alerts_with_regex(error)
    custom_message = search_error_message_by_regex_result(
        connection_account, alerts_with_regex, is_wizard=True
    )
    if custom_message:
        return custom_message

    alert_without_regex = connection_account.integration.get_alert_without_regex(error)
    if alert_without_regex:
        return alert_without_regex.wizard_message

    return error.default_wizard_message if error.default_wizard_message else ''


def get_oldest_connection_account_by_vendor_name(
    organization: Organization, vendor_name: str
) -> ConnectionAccount:
    return (
        ConnectionAccount.objects.filter(
            integration__vendor__name__iexact=vendor_name, organization=organization
        )
        .order_by('id')
        .first()
    )


def join_reversion_messages(messages: List[str]) -> str:
    return ', '.join(msg for msg in messages if msg is not None)


def _configuration_error(
    error_message: str, error_code: str = USER_INPUT_ERROR
) -> ConfigurationError:
    return ConfigurationError(
        error_code=error_code,
        error_message=error_message,
        is_user_input_error=True,
    )


def is_last_execution_within_date_range(
    last_execution_date: Union[datetime, None], tolerance: int = SECONDS_IN_MINUTE * 90
) -> bool:
    if not last_execution_date:
        return True
    delta = datetime.now(timezone.utc) - last_execution_date
    # Delta in seconds + 1.5 hours (seconds)
    delta_seconds = delta.total_seconds() + tolerance
    delta_days = delta_seconds / SECONDS_IN_DAY
    return delta_days > ONE_DAY


def is_optimized_integration(integration: Integration) -> bool:
    return integration.vendor.name.lower() in OPTIMIZED_INTEGRATIONS


def iso_format(date: str):
    return datetime.strptime(date, '%Y-%m-%d').isoformat()


def integration_workers():
    inspect = celery_app.control.inspect()
    workers = []
    for worker, queues in inspect.active_queues().items():
        queue_names = [queue['name'] for queue in queues]
        if LONG_RUN_QUEUE in queue_names:
            workers.append(worker)
    return workers


def get_celery_workers_metrics() -> dict[str, int]:
    workers = {}
    with timeout(seconds=10):
        try:
            workers = celery_app.control.inspect().active()
        except TimeoutException:
            logger.info('Not able to get celery workers information')
            pass
    int_workers = integration_workers()
    total_workers = len(int_workers)
    busy_workers = 0
    for worker in workers:
        if worker in int_workers and len(workers[worker]) > 0:
            busy_workers += 1

    return dict(
        total=total_workers, busy=busy_workers, idle=total_workers - busy_workers
    )


class timeout:
    def __init__(self, seconds=1, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum, frame):
        raise TimeoutException

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        signal.alarm(0)


def is_worker():
    return 'worker' in sys.argv


def push_worker_metric():
    if not is_worker():
        return
    try:
        worker_metrics = get_celery_workers_metrics()
        logger.info(f'Celery Long Workers Status: {worker_metrics}')
        shortage = -1 * worker_metrics['idle'] + 1
        client = boto3.client('cloudwatch', region_name=REGION_NAME)
        client.put_metric_data(
            Namespace='Celery/Workers',
            MetricData=[
                {
                    'MetricName': 'LongWorkerShortage',
                    'Dimensions': [
                        {
                            'Name': 'Source',
                            'Value': 'integrations',
                        },
                        {
                            'Name': 'Env',
                            'Value': os.getenv('ENVIRONMENT'),
                        },
                    ],
                    'Value': shortage if shortage >= 0 else -1,
                    'Unit': 'Count',
                },
            ],
        )
    except ClientError as e:
        logger.error(f'Error to save worker metric {e}')

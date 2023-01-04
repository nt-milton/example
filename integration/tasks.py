import logging
import operator
import time
import timeit
from datetime import datetime, timedelta, timezone
from functools import reduce
from io import StringIO
from typing import Dict, List, Union

from django.core.exceptions import FieldError
from django.db.models import Q
from log_request_id import local

from access_review.evidence import reconcile_access_review_objects
from access_review.models import AccessReview, AccessReviewVendor
from laika.aws.s3 import s3_client
from laika.celery import app as celery_app
from laika.utils.dates import str_date_to_date_formatted
from monitor.events import integration_events
from monitor.steampipe import monitor_context
from monitor.tasks import create_monitors_and_run
from objects.system_types import SERVICE_ACCOUNT, USER
from user.constants import ACTIVE

from .constants import SYNC
from .error_codes import (
    BAD_GATEWAY,
    CONNECTION_TIMEOUT,
    DENIAL_OF_CONSENT,
    EXPIRED_TOKEN,
    GATEWAY_TIMEOUT,
    INSUFFICIENT_PERMISSIONS,
    NONE,
    PROVIDER_SERVER_ERROR,
)
from .exceptions import ConfigurationError
from .factory import get_integration
from .models import ALREADY_EXISTS, ERROR, SUCCESS, ConnectionAccount, Integration
from .settings import INTEGRATIONS_TROUBLESHOOTING_BUCKET
from .test_mode import test_state
from .utils import (
    get_last_run,
    is_last_execution_within_date_range,
    is_optimized_integration,
    push_worker_metric,
)

UPDATED_CONNECTIONS = 'Updated connections'

logger = logging.getLogger('integration_tasks')


def connection_within_interval(
    connection_account: ConnectionAccount,
) -> bool:
    last_execution_date = connection_account.updated_at

    last_run = get_last_run(connection_account)
    if last_run:
        last_execution_date = str_date_to_date_formatted(last_run).replace(
            tzinfo=timezone.utc
        )

    is_within_interval = is_last_execution_within_date_range(
        last_execution_date=last_execution_date,
    )
    if not is_within_interval:
        logger.warning(
            f'Connection account {connection_account.id} '
            'didn\'t run because it\'s not within the interval'
        )
    return is_within_interval


def _time_sync_account_should_run_again() -> datetime:
    # if a connection takes more than 20 hours running, then we try again
    return datetime.now(timezone.utc) - timedelta(hours=20)


@celery_app.task(name='integrations_daily_update')
def update_integrations() -> Dict:
    start_time = timeit.default_timer()
    connections = ConnectionAccount.objects.filter(
        Q(status=SUCCESS)
        | Q(status=ALREADY_EXISTS)
        | (
            Q(status=ERROR)
            & (
                Q(error_code=DENIAL_OF_CONSENT)
                | Q(error_code=CONNECTION_TIMEOUT)
                | Q(error_code=INSUFFICIENT_PERMISSIONS)
                | Q(error_code=PROVIDER_SERVER_ERROR)
                | Q(error_code=BAD_GATEWAY)
                | Q(error_code=GATEWAY_TIMEOUT)
                | Q(error_code=NONE)
            )
            | (
                Q(status=SYNC)
                & (Q(updated_at__lt=_time_sync_account_should_run_again()))
            )
        ),
        organization__state=ACTIVE,
        integration_id__in=Integration.objects.actives(),
    ).order_by('updated_at')
    all_connections_count = connections.count()
    logger.info(
        'Total of connection accounts to be '
        f'executed: {all_connections_count} on Celery Daily Task'
    )
    count = 0
    metrics: Dict = {}
    for connection in connections.all():
        organization = connection.organization
        if connection_within_interval(connection):
            logger.info(
                'Scheduling execution for '
                f'organization: {organization.name} and '
                f'connection account: {connection.id}'
            )
            send_email = (
                False if connection.error_code == PROVIDER_SERVER_ERROR else True
            )
            run_integration.delay(
                connection_id=connection.id, send_mail_error=send_email
            )
            count += 1

    execution_time = timeit.default_timer() - start_time
    metrics['execution_time'] = execution_time
    metrics['executed_connections'] = count
    logger.info(f'Metrics on Integration execution: {metrics}')
    return metrics


@celery_app.task(bind=True, name='Update connections to expired token')
def update_connection_accounts_to_expired_token(
    self, *args, **errors_by_key: Union[Dict[str, str], None]
) -> Dict[str, List]:
    updated_connections: Dict = {UPDATED_CONNECTIONS: []}
    if not errors_by_key:
        logger.info('Not parameters for filter')
        return updated_connections

    lookup_queries_list = [(k, v) for k, v in errors_by_key.items()]
    query_list = [Q(lookup_query) for lookup_query in lookup_queries_list]

    try:
        connections = (
            ConnectionAccount.objects.filter(
                Q(status=ERROR) & reduce(operator.or_, query_list),
                organization__state=ACTIVE,
            )
            .exclude(error_code=EXPIRED_TOKEN)
            .order_by('updated_at')
        )

        for connection in connections:
            connection.error_code = EXPIRED_TOKEN
            connection.save()

            updated_connections[UPDATED_CONNECTIONS].append(connection.id)
            logger.info(
                f'Connection account {connection.id} updated to '
                f'error code {connection.error_code} due result '
                f'{connection.result} has the conditions.'
            )
    except FieldError as fe:
        logger.info(
            'Error to execute query because invalid parameters: '
            f'{query_list}. Error: {str(fe)}'
        )
    return updated_connections


@celery_app.task(name='run_integration')
def run_integration(connection_id, send_mail_error=True) -> dict:
    try:
        connection_account = ConnectionAccount.objects.get(id=connection_id)
        start_time = timeit.default_timer()

        connection_account.send_mail_error = send_mail_error
        _log_execution_connection(connection_account)

        integration = get_integration(connection_account)
        integration.run(connection_account)
        reconcile_access_review_objects(connection_account)

        return execution_stats(start_time, connection_account)
    except ConnectionAccount.DoesNotExist:
        message = f'Connection account with id {connection_id} does not exist.'
        logger.warning(message)
        return {'error': message}
    except Exception as exc:
        message = f'Error running integration with id {connection_id}. Error: {exc}'
        logger.error(message)
        return {'error': message}


def execution_stats(start_time: float, connection_account: ConnectionAccount):
    metrics = {'connection_id': connection_account.id}
    connection_run_time = timeit.default_timer() - start_time
    metrics['total_time'] = connection_run_time
    execution = connection_account.configuration_state.get('execution', {})
    if 'network_wait' in execution:
        metrics['waiting_api_time'] = execution['network_wait']
    return metrics


def _log_execution_connection(connection_account: ConnectionAccount) -> None:
    vendor_name = connection_account.integration.vendor.name
    logger.info(
        f'Running {vendor_name} integration in '
        f'organization: {connection_account.organization.name} by '
        f'connection account id: {connection_account.id} '
        f'with alias: {connection_account.alias}'
    )


@celery_app.task(name='Execute connection accounts')
def execute_connection_accounts(*args) -> Dict:
    if not args:
        return {'executed_connections': 0}

    logger.info(f'Executing connection accounts {args} in celery')
    connection_accounts = ConnectionAccount.objects.filter(
        id__in=args, status__in=[SUCCESS, SYNC, ERROR]
    )

    for connection_account in connection_accounts:
        connection_account.send_mail_error = False
        _log_execution_connection(connection_account)

        run_integration.delay(
            connection_id=connection_account.id, send_mail_error=False
        )

    return {'executed_connections': connection_accounts.count()}


@celery_app.task(name='Run Integration on Test Mode')
def run_integration_on_test_mode(connection_id: int) -> Dict:
    error_message = f'Error running integration with id {connection_id} on Test mode.'

    def _send_file_to_bucket() -> Dict:
        responses_string_io = StringIO()
        responses_string_io.write('\n'.join([r for r in test_state.responses]))
        logger.info(
            f'Sending responses from connection {connection_id} to the S3 Bucket'
        )
        return s3_client.put_object(
            ACL='private',
            Body=responses_string_io.getvalue(),
            Key=f'connection_account-{str(connection_account.id)}',
            Bucket=INTEGRATIONS_TROUBLESHOOTING_BUCKET,
            ContentType='application/json',
        )

    try:
        connection_account: ConnectionAccount = ConnectionAccount.objects.get(
            id=connection_id
        )
        if connection_account.status == SYNC:
            message = (
                "Connection account can't be executed on testing mode "
                "due is on SYNC status"
            )
            logger.warning(message)
            return {'error': error_message + f' Error: {message}'}

        connection_account.send_mail_error = False
        test_state.init(connection_account.id)
        logger.info(f'Running connection {connection_id} in testing mode')
        integration = get_integration(connection_account)
        integration.run(connection_account)
        return {'ETag': _send_file_to_bucket().get("ETag")}
    except Exception as exc:
        logger.error(error_message + f' Error: {exc}')
        return {'ETag': _send_file_to_bucket().get("ETag")}
    finally:
        test_state.reset_test_mode(connection_id)


@celery_app.task(name='Run vendor integrations per organization')
def run_vendor_integrations_per_organization(
    organization_id: str,
    vendor_id: str,
):
    error_message = (
        'Error running integration for organization vendor for '
        f'organization_id: {organization_id} '
        f'vendor_id: {vendor_id} '
        'connection_account_id: {connection_account_id}. '
        'Error: {exception}'
    )
    connection_accounts = ConnectionAccount.objects.filter(
        organization__id=organization_id,
        integration__vendor__id=vendor_id,
    )
    was_successful = False
    for connection_account in connection_accounts:
        try:
            run_connection_account_integration_for_access_review(
                connection_account,
            )
            connection_account.refresh_from_db()
            was_successful = was_successful or connection_account.status == SUCCESS
        except Exception as exception:
            logger.info(
                error_message.format(
                    connection_account_id=connection_account.id, exception=exception
                )
            )
    AccessReviewVendor.objects.filter(
        access_review__organization__id=organization_id,
        access_review__status=AccessReview.Status.IN_PROGRESS,
        vendor__id=vendor_id,
    ).update(synced_at=datetime.now())
    if not was_successful:
        raise ConfigurationError('Could not sync vendors')
    return {'success': was_successful}


@celery_app.task(name='run_initial_and_notify_monitors')
def run_initial_and_notify_monitors(connection_account_id):
    connection_account = ConnectionAccount.objects.get(id=connection_account_id)
    run_and_notify_connection(connection_account)


def run_and_notify_connection(connection_account: ConnectionAccount, request_id=None):
    if request_id:
        local.request_id = request_id
    test_state.reset_test_mode(connection_account.id)
    integration = get_integration(connection_account)
    integration.run(connection_account)
    reconcile_access_review_objects(connection_account)
    with monitor_context(connection_account):
        create_monitors_and_run(
            connection_account.organization,
            integration_events(
                connection_account.integration.vendor.name,
                connection_account.integration.laika_objects(),
            ),
        )


def run_connection_account_integration_for_access_review(
    connection_account: ConnectionAccount,
):
    integration = get_integration(connection_account)
    if is_optimized_integration(connection_account.integration):
        integration.run_by_lo_types(
            connection_account, [USER.type, SERVICE_ACCOUNT.type]
        )
    else:
        integration.run(connection_account)
    reconcile_access_review_objects(connection_account)


@celery_app.task(name='workers_metric')
def workers_metric() -> None:
    push_worker_metric()


@celery_app.task(name='scale_simulator')
def scale_simulator(*args) -> None:
    for sleep in args:
        simulator.delay(sleep)


@celery_app.task(name='simulator')
def simulator(sleep: int) -> None:
    logger.info(f'Running scale simulator sleep {sleep}')
    time.sleep(sleep)
    logger.info(f'Sleep {sleep} done')


@celery_app.task(name='reconcile_sync_connections')
def reconcile_sync_connections(time_in_seconds: int) -> None:
    workers = celery_app.control.inspect().active().values()
    connection_accounts = ConnectionAccount.objects.filter(
        status=SYNC,
        updated_at__lt=datetime.now(timezone.utc) + timedelta(seconds=time_in_seconds),
    ).values_list('id', flat=True)
    integrations_jobs = []
    for tasks in workers:
        for job in tasks:
            if job.get('type') in [
                'run_integration',
                'run_initial_and_notify_monitors',
            ]:
                integrations_jobs.append(job.get('args')[0])
    phantom_jobs = set(connection_accounts).difference(integrations_jobs)
    for connection_account_id in phantom_jobs:
        run_integration.delay(
            connection_id=connection_account_id, send_mail_error=False
        )

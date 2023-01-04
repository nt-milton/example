import contextlib
import logging
import os
import subprocess  # nosec
import sys
import time
import timeit
from pathlib import Path

import psycopg2
from django.db import DatabaseError
from psycopg2 import OperationalError
from sqlparse.sql import Comparison, Parenthesis, Token
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_incrementing,
)

from integration.constants import (
    AWS_VENDOR,
    AZURE_VENDOR,
    DIGITALOCEAN,
    GCP_VENDOR,
    HEROKU_VENDOR,
    OKTA_VENDOR,
)
from integration.error_codes import OTHER
from integration.exceptions import ConfigurationError
from integration.models import SUCCESS, ConnectionAccount
from monitor.result import AggregateResult, Result
from monitor.sqlutils import (
    extract_vendor,
    get_selected_tables,
    get_tokens,
    is_cloud_table,
)
from monitor.steampipe_configurations.aws import get_aws_configuration
from monitor.steampipe_configurations.azure import get_azure_configuration
from monitor.steampipe_configurations.digitalocean import get_digitalocean_configuration
from monitor.steampipe_configurations.gcp import get_gcp_configuration
from monitor.steampipe_configurations.heroku import get_heroku_configuration
from monitor.steampipe_configurations.okta import get_okta_configuration
from organization.models import ACTIVE, Organization

vendors = {
    'aws': AWS_VENDOR,
    'gcp': GCP_VENDOR,
    'azure': AZURE_VENDOR,
    'heroku': HEROKU_VENDOR,
    'okta': OKTA_VENDOR,
    'digitalocean': DIGITALOCEAN,
}

configuration_builders = {
    AWS_VENDOR: get_aws_configuration,
    GCP_VENDOR: get_gcp_configuration,
    AZURE_VENDOR: get_azure_configuration,
    HEROKU_VENDOR: get_heroku_configuration,
    OKTA_VENDOR: get_okta_configuration,
    DIGITALOCEAN: get_digitalocean_configuration,
}

logger = logging.getLogger(__name__)

STEAMPIPE_SERVICE_START = (
    'steampipe service start --database-password \'\' --database-listen local'
).split()
STEAMPIPE_SERVICE_RESTART = 'steampipe service restart'.split()
STEAMPIPE_TIMEOUT = 120
STEAMPIPE_DATABASE_CONNECTION_LOST = 'could not establish connection with database'
STEAMPIPE_PORT_ALREADY_USED = 'Cannot listen on port'
STEAMPIPE_SESSION_CONFLICT = 'session open. To run multiple sessions, first run'
STEAMPIPE_DSN = 'postgres://steampipe:@localhost:9193/steampipe'
SECONDS_PER_MINUTE = 60
CREDENTIALS_REFRESH_INTERVAL = 50 * SECONDS_PER_MINUTE


def is_api_or_worker():
    is_api = 'runserver' in sys.argv
    is_worker = 'worker' in sys.argv
    return is_api or is_worker


def init_steampipe_service():
    if is_api_or_worker():
        subprocess.run(STEAMPIPE_SERVICE_START, capture_output=True)  # nosec


def restart_steampipe_service():
    if is_api_or_worker():
        subprocess.run(STEAMPIPE_SERVICE_RESTART, capture_output=True)  # nosec


init_steampipe_service()


def build_profile_name(id: int):
    return f'profile_{id}'.replace('-', '_')


def verify_steampipe_table(token: Token) -> bool:
    return is_cloud_table(token.value)


def build_raw_steampipe_query(connection_account: ConnectionAccount, query: str) -> str:
    profile_name = build_profile_name(connection_account.id)
    return add_profile_query(profile_name, query)


def subquery_replace(profile: str, query: str) -> str:
    tokens = get_tokens(query)
    subqueries = {}
    for token in tokens:
        if token.is_group and token.tokens[0].normalized == 'WHERE':
            comparisons = [
                nested for nested in token.tokens if isinstance(nested, Comparison)
            ]
            for comparison in comparisons:
                sq = subquery(comparison)
                if sq:
                    subqueries[sq] = add_profile_query(profile, sq)
    for k, v in subqueries.items():
        query = query.replace(k, v)
    return query


def subquery(comparison: Comparison):
    nested = [nested for nested in comparison.tokens if isinstance(nested, Parenthesis)]
    if not nested:
        return None
    return nested[0].value


def parenthesis_enclosed(query: str) -> bool:
    tokens = get_tokens(query)
    return len(tokens) == 1 and tokens[0].is_group and tokens[0].tokens[0].value == '('


def add_profile_query(profile_name, query: str) -> str:
    if parenthesis_enclosed(query):
        return f'({add_profile_query(profile_name, query[1:-1])})'
    selected_tables = get_selected_tables(query, verify_table=verify_steampipe_table)
    tokens = get_tokens(query)
    for index, _, _ in selected_tables:
        table_name = tokens[index].value
        schema = profile_name
        if table_name.startswith('azuread_'):
            schema = f'azuread_{profile_name}'
        tokens[index].value = f'{schema}.{table_name}'
    token_values = [token.value for token in tokens]
    return subquery_replace(profile_name, ''.join(token_values))


def run(organization: Organization, query: str) -> Result:
    vendor_name = get_vendor_name_from_query(query)
    connection_accounts = ConnectionAccount.objects.filter(
        status=SUCCESS,
        configuration_state__credentials__isnull=False,
        integration__vendor__name=vendor_name,
        organization=organization,
    )
    results = []
    for connection_account in connection_accounts:
        raw_query = build_raw_steampipe_query(connection_account, query)
        create_profile(connection_account)
        results.append(run_query(raw_query))
    return AggregateResult(results=results)


def validate_worker_profile(connection_account: ConnectionAccount):
    folder = f'{Path.home()}/.steampipe/config'
    profile_name = f'profile_{connection_account.id}'
    if not os.path.exists(f'{folder}/{profile_name}.spc'):
        raise ConfigurationError(
            OTHER, f'no config found for connection {profile_name}'
        )


def profile_file_path(cnn_id: int) -> str:
    profile_name = build_profile_name(cnn_id)
    return f'{Path.home()}/.steampipe/config/{profile_name}.spc'


def refresh_required(profile_file: str) -> bool:
    delta = time.time() - os.path.getmtime(profile_file)
    return delta > CREDENTIALS_REFRESH_INTERVAL


def create_profile(connection_account: ConnectionAccount):
    if 'worker' in sys.argv:
        return validate_worker_profile(connection_account)
    profile_file = profile_file_path(connection_account.id)
    if not os.path.exists(profile_file) or refresh_required(profile_file):
        create_profile_before_run(connection_account)
        restart_steampipe_service()


def create_profile_before_run(connection_account: ConnectionAccount):
    profile_name = build_profile_name(connection_account.id)
    profile_file = profile_file_path(connection_account.id)
    vendor_name = connection_account.integration.vendor.name
    configuration_builder = configuration_builders[vendor_name]
    configuration = configuration_builder(profile_name, connection_account)
    with open(profile_file, 'w') as writer:
        writer.write(configuration)


def get_vendor_name_from_query(query: str) -> str:
    selected_tables = get_selected_tables(query, verify_table=verify_steampipe_table)
    table_name = selected_tables[0][1] if len(selected_tables) > 0 else None
    if table_name is None:
        raise DatabaseError('Invalid table selection')
    vendor_name = get_vendor_from_table_name(table_name)
    if vendor_name is None:
        raise DatabaseError(f'No vendor found for identifier {vendor_name}')
    else:
        return vendor_name


def get_vendor_from_table_name(table_name):
    vendor_name = extract_vendor(table_name)
    return vendors.get(vendor_name, None)


def is_steampipe_broken(error_message):
    return (
        STEAMPIPE_DATABASE_CONNECTION_LOST in error_message
        or STEAMPIPE_PORT_ALREADY_USED in error_message
        or STEAMPIPE_SESSION_CONFLICT in error_message
    )


def restart_required(exception):
    return is_steampipe_broken(str(exception))


def run_query(query: str) -> Result:
    return query_database_service(query)


def log_steampipe_attempt(*args):
    restart_steampipe_service()


@retry(
    wait=wait_incrementing(start=4, increment=10, max=100),
    stop=stop_after_attempt(3),
    reraise=True,
    retry=retry_if_exception_type(OperationalError),
    after=log_steampipe_attempt,
)
def query_database_service(query: str) -> Result:
    connection = psycopg2.connect(STEAMPIPE_DSN)
    try:
        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            return Result(columns=columns, data=cursor.fetchall())
    except Exception as error:
        error_message = str(error)
        if is_steampipe_broken(error_message):
            logger.exception(f'Steampipe issue {error_message}')
            raise OSError(error_message)
        else:
            raise DatabaseError(f'Steampipe error: {error_message}')
    finally:
        connection.close()


@contextlib.contextmanager
def steampipe_context(connection_account: ConnectionAccount):
    try:
        create_profiles_for_task(
            connection_account.organization.id,
            connection_account.integration.vendor.name,
        )
        yield
    finally:
        clean_steampipe_environment()


def monitor_context(connection_account: ConnectionAccount):
    vendor_name = connection_account.integration.vendor.name
    is_csp = vendor_name in configuration_builders
    return steampipe_context(connection_account) if is_csp else contextlib.nullcontext()


def remove_organization_profiles():
    home = str(Path.home())
    folder = f'{home}/.steampipe/config'
    for root, _, files in os.walk(folder):
        profiles = [f for f in files if f.startswith('profile')]
        for profile in profiles:
            os.remove(os.path.join(root, profile))


def clean_steampipe_environment():
    try:
        remove_organization_profiles()
    except FileNotFoundError:
        logger.info('Running on testing mode')


def create_profiles_for_task(org_id: str, vendor: str = '') -> None:
    profile_setup_start = timeit.default_timer()
    cloud_vendors = [vendor] if vendor else configuration_builders.keys()
    connection_accounts = ConnectionAccount.objects.filter(
        status=SUCCESS,
        configuration_state__credentials__isnull=False,
        integration__vendor__name__in=cloud_vendors,
        organization__state=ACTIVE,
        organization__id=org_id,
    )
    for connection_account in connection_accounts:
        logger.info(f'Creating profile for connection account: {connection_account.id}')
        try:
            create_profile_before_run(connection_account)
        except Exception:
            logger.info(
                f'The profile for connection account: {connection_account.id} '
                'could not be created'
            )
    profile_setup_time = timeit.default_timer() - profile_setup_start
    logger.info(f'Steampipe profile setup took: {profile_setup_time} seconds')
    restart_start = timeit.default_timer()
    restart_steampipe_service()
    restart_time = timeit.default_timer() - restart_start
    logger.info(f'Steampipe restart took: {restart_time} seconds')

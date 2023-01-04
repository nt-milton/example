import logging
from datetime import datetime
from typing import List, Tuple, Union

from objects.system_types import EVENT, MONITOR, SERVICE_ACCOUNT, USER

from ..account import get_integration_laika_objects, integrate_account
from ..encryption_utils import decrypt_value, get_decrypted_or_encrypted_value
from ..exceptions import ConfigurationError, ConnectionAlreadyExists
from ..models import ConnectionAccount
from ..settings import DATADOG_SITES, DATADOG_US_API_URL
from ..store import Mapper, clean_up_by_criteria, update_laika_objects
from ..utils import calculate_date_range, get_last_run, iso_format
from .mapper import (
    map_event_response_to_laika_object,
    map_monitor_response_to_laika_object,
    map_service_account_to_laika_object,
    map_users_response_to_laika_object,
)
from .rest_client import (
    get_managed_organizations,
    list_monitors,
    pull_events,
    read_all_datadog_users,
)
from .utils import (
    INVALID_CREDENTIALS_OR_LACK_PERMISSIONS_ALERT,
    create_datadog_service_account,
    create_datadog_user,
    get_organizations_mapped,
    get_page_roles,
)

logger = logging.getLogger(__name__)

DATADOG_SYSTEM = 'Datadog'
N_RECORDS = get_integration_laika_objects(DATADOG_SYSTEM)


def _get_site(connection_account: ConnectionAccount) -> str:
    return connection_account.authentication.get('site', DATADOG_US_API_URL)


def run(connection_account: ConnectionAccount):
    run_by_lo_types(connection_account, [])


def run_by_lo_types(connection_account: ConnectionAccount, lo_types: list[str]):
    with connection_account.connection_attempt():
        raise_if_duplicate(connection_account)
        api_key, application_key = keys(connection_account)
        datasets = connection_account.settings.get('datasets', [])
        if MONITOR.type in datasets and not lo_types:
            integrate_monitors(connection_account, api_key, application_key)
        # TODO: remove events code
        integrate_users(
            connection_account=connection_account,
            api_key=api_key,
            application_key=application_key,
        )
        integrate_service_accounts(
            connection_account=connection_account,
            api_key=api_key,
            application_key=application_key,
        )
        integrate_account(
            connection_account=connection_account,
            source_system=DATADOG_SYSTEM,
            records_dict=N_RECORDS,
        )


def get_valid_datadog_site(
    api_key: str,
    application_key: str,
) -> Union[tuple[str, bool], tuple[list[dict], bool]]:
    errors: list[dict] = []
    for site in DATADOG_SITES:
        site_result = list_monitors(site, api_key, application_key)
        if 'errors' not in site_result:
            return site, False
        else:
            errors.append(dict(site=site, error=site_result))

    return errors, True


def connect(connection_account: ConnectionAccount):
    with connection_account.connection_error(
        error_code=INVALID_CREDENTIALS_OR_LACK_PERMISSIONS_ALERT
    ):
        api_key, application_key = keys(connection_account)
        valid_site, has_errors = get_valid_datadog_site(api_key, application_key)
        if has_errors:
            raise ConfigurationError.bad_client_credentials(response=valid_site)
        connection_account.authentication['site'] = valid_site
        connection_account.save()


def integrate_monitors(
    connection_account: ConnectionAccount, api_key: str, application_key: str
):
    monitor_mapper = Mapper(
        map_function=map_monitor_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=MONITOR,
    )
    site = _get_site(connection_account)
    records = list_monitors(
        site=site,
        api_key=api_key,
        application_key=application_key,
        raise_exception=True,
    )
    update_laika_objects(connection_account, monitor_mapper, records)


def integrate_events(
    connection_account: ConnectionAccount, api_key: str, application_key: str
):
    start_timestamp = _get_start_timestamp(connection_account)

    def store(records: list):
        _store_events(connection_account, records)

    pull_events(
        site=_get_site(connection_account),
        api_key=api_key,
        application_key=application_key,
        start=start_timestamp,
        store_events=store,
        chunk_size=_get_chunk_size(connection_account),
    )
    selected_time_range = calculate_date_range()
    clean_up_by_criteria(
        connection_account,
        EVENT,
        lookup_query={'data__Event date__gt': iso_format(selected_time_range)},
    )


def _store_events(connection_account: ConnectionAccount, records: List):
    event_mapper = Mapper(
        map_function=map_event_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=EVENT,
    )

    update_laika_objects(
        connection_account=connection_account,
        mapper=event_mapper,
        raw_objects=records,
        cleanup_objects=False,
    )


def _get_managed_organizations(
    connection_account: ConnectionAccount, api_key: str, application_key: str
) -> List:
    response = get_managed_organizations(
        site=_get_site(connection_account),
        api_key=api_key,
        application_key=application_key,
    )
    return response.get('orgs', []) if response else []


def integrate_users(
    connection_account: ConnectionAccount, api_key: str, application_key: str
):
    def _get_mapped_users():
        users_values = read_all_datadog_users(
            site=_get_site(connection_account),
            api_key=api_key,
            application_key=application_key,
        )
        organizations = _get_managed_organizations(
            connection_account=connection_account,
            api_key=api_key,
            application_key=application_key,
        )
        for values in users_values:
            all_roles = get_page_roles(response_values=values)
            for user in values.get('data'):
                yield create_datadog_user(
                    user=user,
                    organizations=get_organizations_mapped(organizations),
                    all_roles=all_roles,
                )

    users = _get_mapped_users()
    users_mapper = Mapper(
        map_function=map_users_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=USER,
    )

    update_laika_objects(
        connection_account=connection_account, mapper=users_mapper, raw_objects=users
    )


def integrate_service_accounts(
    connection_account: ConnectionAccount, api_key: str, application_key: str
):
    def _get_mapped_service_accounts():
        users_values = read_all_datadog_users(
            site=_get_site(connection_account),
            api_key=api_key,
            application_key=application_key,
            filter_service_account=True,
        )
        for values in users_values:
            all_roles = get_page_roles(response_values=values)
            for service_account in values.get('data'):
                yield create_datadog_service_account(
                    service_account=service_account,
                    all_roles=all_roles,
                )

    service_accounts = _get_mapped_service_accounts()
    service_accounts_mapper = Mapper(
        map_function=map_service_account_to_laika_object,
        keys=['Id'],
        laika_object_spec=SERVICE_ACCOUNT,
    )

    update_laika_objects(
        connection_account=connection_account,
        mapper=service_accounts_mapper,
        raw_objects=service_accounts,
    )


def raise_if_duplicate(connection_account: ConnectionAccount):
    api_key, application_key = keys(connection_account)
    data_dog_connection_accounts: list[
        ConnectionAccount
    ] = ConnectionAccount.objects.filter(
        organization=connection_account.organization,
        integration=connection_account.integration,
    ).exclude(
        id=connection_account.id
    )
    for data_dog_connection_account in data_dog_connection_accounts:
        decrypted_api_key = get_decrypted_or_encrypted_value(
            'apiKey', data_dog_connection_account
        )
        decrypted_application_key = get_decrypted_or_encrypted_value(
            'programKey', data_dog_connection_account
        )
        if decrypted_api_key == decrypt_value(
            api_key
        ) and decrypted_application_key == decrypt_value(application_key):
            raise ConnectionAlreadyExists()


def keys(connection_account: ConnectionAccount) -> Tuple[str, str]:
    credential = connection_account.configuration_state.get('credentials')
    get_decrypted_or_encrypted_value('apiKey', connection_account)
    get_decrypted_or_encrypted_value('programKey', connection_account)
    return credential.get('apiKey'), credential.get('programKey')


def _get_start_timestamp(connection_account: ConnectionAccount) -> Union[float, None]:
    last_run = get_last_run(connection_account)
    start_timestamp = None
    if last_run:
        last_run_date = datetime.strptime(last_run, '%Y-%m-%d')
        start_timestamp = datetime.timestamp(last_run_date)
    return start_timestamp


def _get_chunk_size(connection_account: ConnectionAccount) -> int:
    return connection_account.integration.metadata.get('chunk_size', 1000)

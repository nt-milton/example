import timeit
from datetime import datetime
from typing import Any, Dict

from integration.log_utils import connection_context
from integration.models import ConnectionAccount
from integration.store import Mapper, update_laika_objects
from objects.models import LaikaObject
from objects.system_types import ACCOUNT, Account

JSONType = Dict[str, Any]
DEL_PREFIX = 'deleted'
PEOPLE_KEYS = ['people', 'people_discovered']


def integrate_account(connection_account, source_system, records_dict):
    def map(*args):
        return _map_account_to_laika_object(
            connection_account,
            source_system,
            set_connection_account_number_of_records(connection_account, records_dict),
        )

    account_mapper = Mapper(
        map_function=map,
        keys=['Source System', 'Connection Name'],
        laika_object_spec=ACCOUNT,
    )
    update_laika_objects(connection_account, account_mapper, [{}])
    set_execution_stats(connection_account)


def _map_account_to_laika_object(connection_account, source_system, records_dict):
    lo_account = Account()
    lo_account.is_active = True
    lo_account.created_on = connection_account.created_at.isoformat()
    lo_account.updated_on = datetime.now().isoformat()
    lo_account.owner = _get_owner_data(connection_account)
    lo_account.number_of_records = str(records_dict)
    lo_account.source_system = source_system
    lo_account.connection_name = connection_account.alias
    return lo_account.data()


def _get_owner_data(connection_account: ConnectionAccount) -> JSONType:
    return {
        'id': connection_account.created_by.id,
        'email': connection_account.created_by.email,
        'firstName': connection_account.created_by.first_name,
        'lastName': connection_account.created_by.last_name,
        'username': connection_account.created_by.username,
    }


def set_connection_account_number_of_records(
    connection_account: ConnectionAccount, n_records_dict: Dict
) -> Dict:
    laika_objects_types = list(n_records_dict.keys())
    for lo_type in laika_objects_types:
        prefix_not_in_lo_type = DEL_PREFIX.lower() not in lo_type.lower()
        if lo_type not in PEOPLE_KEYS and prefix_not_in_lo_type:
            n_records_dict[lo_type] = LaikaObject.objects.filter(
                connection_account__id=connection_account.id,
                object_type__type_name=lo_type,
            ).count()
            n_records_dict[
                f"{DEL_PREFIX.capitalize()}_{lo_type.lower()}"
            ] = LaikaObject.objects.filter(
                connection_account__id=connection_account.id,
                deleted_at__isnull=False,
                object_type__type_name=lo_type,
            ).count()
    number_of_records_dict = {
        key.capitalize(): value for key, value in n_records_dict.items()
    }
    connection_account.result = number_of_records_dict
    return number_of_records_dict


def set_execution_stats(connection_account: ConnectionAccount):
    context = connection_context.get()
    if context:
        state = connection_account.configuration_state
        execution = state.setdefault('execution', {})
        execution['total'] = timeit.default_timer() - context.start_time
        if context.network_wait:
            execution['network_wait'] = context.network_wait

        if context.retries:
            execution['retries'] = context.retries

        if context.network_calls:
            execution['network_calls'] = context.network_calls

        if context.custom_metric:
            execution['custom_metric'] = context.custom_metric
        else:
            execution.pop('custom_metric', None)


def get_integration_laika_objects(integration_name: str):
    integrations = {
        'Asana': {"user": 0, "change_request": 0},
        'Amazon Web Services (AWS)': {"user": 0, "service_account": 0},
        'Microsoft Azure': {"user": 0, "service_account": 0},
        'Bitbucket': {"user": 0, "pull_request": 0, "repository": 0},
        'Shortcut': {"user": 0, "change_request": 0},
        'Datadog': {"user": 0, "monitor": 0, "event": 0, "service_account": 0},
        'Google Cloud Platform (GCP)': {"user": 0, "service_account": 0},
        'GitHub': {"user": 0, "pull_request": 0, "repository": 0},
        'GitHub Apps': {"user": 0, "pull_request": 0, "repository": 0},
        'GitLab': {"user": 0, "pull_request": 0, "repository": 0},
        'Google Workspace': {"user": 0, "vendor_candidate": 0},
        'Heroku': {"user": 0},
        'Jamf': {"device": 0},
        'Jira': {"user": 0, "change_request": 0},
        'Linear': {"user": 0, "change_request": 0},
        'Microsoft 365': {"user": 0, "device": 0, "vendor_candidate": 0},
        'Okta': {"user": 0},
        'Rippling': {"user": 0, "device": 0, "people": 0, "people_discovered": 0},
        'Sentry': {"user": 0, "monitor": 0, "event": 0},
        'Vetty': {"background_check": 0},
        'Slack': {"user": 0},
        'checkr': {'background_check': 0},
        'Azure DevOps': {"user": 0, "pull_request": 0, "repository": 0},
        'Azure Boards': {"change_request": 0},
        'Microsoft Intune': {"device": 0},
        'Jumpcloud': {"user": 0},
        'DigitalOcean': {"monitor": 0},
        'Auth0': {"user": 0},
    }
    return integrations[integration_name]

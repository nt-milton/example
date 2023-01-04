from typing import Any, Callable

from integration.account import get_integration_laika_objects, integrate_account
from integration.encryption_utils import get_decrypted_or_encrypted_value
from integration.exceptions import ConnectionAlreadyExists
from integration.jumpcloud import rest_client
from integration.jumpcloud.constants import INVALID_JUMPCLOUD_API_KEY, JUMPCLOUD, STEPS
from integration.jumpcloud.mapper import build_mapper_from_user_to_laika_object
from integration.models import ConnectionAccount
from integration.store import Mapper, update_laika_objects
from integration.types import FieldOptionsResponseType
from integration.utils import prefetch
from objects.system_types import USER

N_RECORDS = get_integration_laika_objects(JUMPCLOUD)


def run(connection_account: ConnectionAccount):
    with connection_account.connection_attempt():
        raise_if_duplicate(connection_account)
        api_key = get_api_key(connection_account)
        integrate_users(connection_account=connection_account, api_key=api_key)
        integrate_account(connection_account, JUMPCLOUD, N_RECORDS)


def get_api_key(connection_account: ConnectionAccount) -> str:
    return get_decrypted_or_encrypted_value('apiKey', connection_account)


def raise_if_duplicate(connection_account: ConnectionAccount):
    api_key = get_api_key(connection_account)
    connection_accounts = ConnectionAccount.objects.filter(
        organization=connection_account.organization,
        integration=connection_account.integration,
    ).exclude(id=connection_account.id)
    selected_organizations = connection_account.settings.get(
        'selectedOrganizations', []
    )
    for current_connection_account in connection_accounts:
        decrypted_api_key = get_decrypted_or_encrypted_value(
            'apiKey', current_connection_account
        )
        selected_organizations_match = (
            selected_organizations
            == current_connection_account.settings.get('selectedOrganizations', [])
        )
        if api_key == decrypted_api_key or selected_organizations_match:
            raise ConnectionAlreadyExists()


def _get_paginated_users(user_requestor: Callable, api_key: str, organization_id: str):
    users = []
    total_count = 0
    current_index = 0
    has_next_page = True
    while has_next_page:
        users_response = user_requestor(
            access_token=api_key,
            organization_id=organization_id,
            limit=STEPS,
            skip=current_index,
        )
        users_page = users_response.json()
        total_count = total_count or users_page.get('totalCount', 0)
        current_index = current_index + STEPS
        has_next_page = total_count >= current_index
        users.extend(users_page.get('results', []))
    return users


def _get_users_from_organization(api_key: str, organization_id) -> list[Any]:
    users = _get_paginated_users(rest_client.get_users, api_key, organization_id)
    system_users = _get_paginated_users(
        rest_client.get_system_users, api_key, organization_id
    )
    return users + system_users


def _get_prefetched_organization_ids(
    connection_account: ConnectionAccount,
) -> list[str]:
    prefetched_organizations = connection_account.authentication.get(
        'prefetch_organization', []
    )
    return [organization['id'] for organization in prefetched_organizations]


def _get_selected_organizations(connection_account: ConnectionAccount) -> list[str]:
    selected_organizations = connection_account.settings.get(
        'selectedOrganizations', []
    )
    fetch_all = 'all' in selected_organizations
    prefetched_organization_ids = _get_prefetched_organization_ids(connection_account)
    return prefetched_organization_ids if fetch_all else selected_organizations


def integrate_users(connection_account: ConnectionAccount, api_key: str):
    users = []
    for organization_id in _get_selected_organizations(connection_account):
        users.extend(_get_users_from_organization(api_key, organization_id))
    users_mapper = Mapper(
        map_function=build_mapper_from_user_to_laika_object(connection_account),
        keys=['Id'],
        laika_object_spec=USER,
    )
    update_laika_objects(
        connection_account=connection_account, mapper=users_mapper, raw_objects=users
    )


def connect(connection_account: ConnectionAccount):
    with connection_account.connection_error(error_code=INVALID_JUMPCLOUD_API_KEY):
        prefetch(connection_account, 'organization')


def get_custom_field_options(
    field_name: str, connection_account: ConnectionAccount
) -> FieldOptionsResponseType:
    api_key = get_api_key(connection_account)
    if field_name == 'organization':
        organizations = rest_client.get_organizations(api_key).json()['results']
        return _get_organizations_options(organizations)
    else:
        raise NotImplementedError('Not implemented')


def _get_organizations_options(organizations) -> FieldOptionsResponseType:
    organization_options = [
        {'id': organization['id'], 'value': {'name': organization['displayName']}}
        for organization in organizations
    ]
    return FieldOptionsResponseType(options=organization_options)

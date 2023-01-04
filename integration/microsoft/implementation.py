import logging

import integration.integration_utils.token_utils as token_utils
from integration.account import get_integration_laika_objects, integrate_account
from integration.discovery import (
    create_vendor_discovery_alert,
    exclude_existing_vendor_candidates,
    get_discovery_status_for_new_vendor_candidate,
    get_vendor_if_it_exists,
    validate_scopes_for_vendor_candidates,
)
from integration.exceptions import ConfigurationError, ConnectionAlreadyExists
from integration.integration_utils.microsoft_utils import MicrosoftRequest
from integration.integration_utils.vendor_users import (
    create_sso_users,
    show_vendor_user_log,
)
from integration.microsoft.mapper import map_devices_response, map_users_response
from integration.microsoft.rest_client import (
    create_refresh_token,
    get_devices,
    get_groups,
    get_organization,
    get_sign_ins_names,
    get_users_by_group,
)
from integration.models import ConnectionAccount
from integration.store import Mapper, update_laika_objects
from integration.types import FieldOptionsResponseType
from integration.utils import prefetch
from objects.system_types import ACCOUNT, DEVICE, USER, resolve_laika_object_type
from vendor.models import VendorCandidate

MICROSOFT_SYSTEM = 'Microsoft 365'
GLOBAL_ADMIN = 'Global Administrator'
VENDOR_SCOPES = 'https://graph.microsoft.com/AuditLog.Read.All'
N_RECORDS = get_integration_laika_objects(MICROSOFT_SYSTEM)

logger_name = __name__
logger = logging.getLogger(logger_name)


def _map_user_response_to_laika_object(response, connection_name):
    return map_users_response(response, connection_name, MICROSOFT_SYSTEM)


def _map_device_response_to_laika_object(response, connection_name):
    return map_devices_response(response, connection_name, MICROSOFT_SYSTEM)


def get_vendor_names(connection_account: ConnectionAccount):
    token_provider = token_utils.build_fetch_token(connection_account)
    delta = connection_account.configuration_state.get('delta', '')
    return get_sign_ins_names(token_provider, delta)


def callback(code, redirect_uri, connection_account):
    if not code:
        raise ConfigurationError.denial_of_consent()

    response = create_refresh_token(code, redirect_uri)
    organization = connection_account.organization
    connection_account.authentication = response
    resolve_laika_object_type(organization, ACCOUNT)
    resolve_laika_object_type(organization, USER)
    resolve_laika_object_type(organization, DEVICE)
    if 'refresh_token' in response:
        prefetch(connection_account, 'group')
    connection_account.save()
    return connection_account


def run(connection_account: ConnectionAccount):
    with connection_account.connection_attempt():
        integrate_users(connection_account)
        if validate_scopes_for_vendor_candidates(connection_account, VENDOR_SCOPES):
            new_vendors = integrate_vendor_candidates(connection_account)
            create_vendor_discovery_alert(connection_account, new_vendors)
        integrate_devices(connection_account)
        integrate_account(connection_account, MICROSOFT_SYSTEM, N_RECORDS)


def integrate_vendor_candidates(connection_account: ConnectionAccount):
    logger.info(
        'Integrating vendor candidates for Microsoft - '
        f'Connection account {connection_account.id}'
    )
    microsoft_vendors: list[dict] = list(get_vendor_names(connection_account))
    if microsoft_vendors:
        connection_account.configuration_state['delta'] = microsoft_vendors[0].get(
            'createdDateTime', ''
        )
    vendor_candidates = []
    vendor_candidate_names = list(
        exclude_existing_vendor_candidates(
            connection_account.organization,
            {sign_in['appDisplayName'] for sign_in in microsoft_vendors},
        )
    )
    logger.info(
        f'Creating Microsoft 365 SSO Users - Connection account {connection_account.id}'
    )
    create_sso_users(
        connection_account, generate_vendor_users(microsoft_vendors, connection_account)
    )
    for vendor_candidate_name in vendor_candidate_names:
        vendor = get_vendor_if_it_exists(vendor_candidate_name)
        status = get_discovery_status_for_new_vendor_candidate(
            connection_account.organization, vendor
        )
        vendor_candidate = VendorCandidate(
            name=vendor_candidate_name,
            organization=connection_account.organization,
            vendor=vendor,
            status=status,
            number_of_users=total_users_in_vendor_discovery(
                microsoft_vendors, vendor_candidate_name
            ),
        )
        vendor_candidates.append(vendor_candidate)
    N_RECORDS["vendor_candidate"] = len(vendor_candidates)
    return VendorCandidate.objects.bulk_create(vendor_candidates)


def integrate_users(connection_account: ConnectionAccount):
    token = token_utils.get_access_token(connection_account)
    validate_groups(connection_account, token)
    groups = connection_account.settings.get('groups')
    raise_if_duplicate(connection_account)
    organization = get_organization(token)
    users = _read_group_users(
        groups=groups, access_token=token, organization=organization
    )
    user_mapper = Mapper(
        map_function=_map_user_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=USER,
    )
    update_laika_objects(connection_account, user_mapper, users)


def integrate_devices(connection_account: ConnectionAccount):
    token = token_utils.get_access_token(connection_account)
    devices = get_devices(token)
    user_mapper = Mapper(
        map_function=_map_device_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=DEVICE,
    )
    update_laika_objects(connection_account, user_mapper, devices)


def _read_group_users(
    groups,
    access_token,
    organization,
):
    for group in groups:
        users = get_users_by_group(access_token=access_token, group_id=group)
        for groups, user, roles in users:
            yield MicrosoftRequest(groups, user, organization, roles)


def get_custom_field_options(field_name: str, connection_account: ConnectionAccount):
    if field_name != 'group':
        raise NotImplementedError('Not implemented')
    return _get_group_options(connection_account)


def _get_group_options(
    connection_account: ConnectionAccount,
):
    token = token_utils.get_access_token(connection_account)
    groups = get_groups(token)
    group_options = []
    for group in groups:
        group_options.append(_map_group_options(group))
    return FieldOptionsResponseType(options=group_options)


def raise_if_duplicate(connection_account):
    groups = connection_account.settings.get('groups')
    if groups is not None:
        exists = (
            ConnectionAccount.objects.actives(
                configuration_state__settings__groups__contains=groups,
                organization=connection_account.organization,
            )
            .exclude(id=connection_account.id)
            .exists()
        )
        if exists:
            raise ConnectionAlreadyExists()


def total_users_in_vendor_discovery(vendor_names: list, vendor_candidate: str) -> int:
    users = set()
    for vendor in vendor_names:
        if vendor.get('appDisplayName') == vendor_candidate:
            status = vendor.get('status')
            if status.get('errorCode') == 0:
                users.add(vendor.get('userId'))
    return len(users)


def generate_vendor_users(
    microsoft_vendors: list, connection_account: ConnectionAccount
) -> dict:
    vendor_users: dict = {}
    for vendor in microsoft_vendors:
        vendor_name = vendor.get('appDisplayName', '')
        user = {
            'name': {'fullName': vendor.get('userDisplayName', '')},
            'primaryEmail': vendor.get('userPrincipalName', ''),
        }
        user_exists = False
        if vendor_name in vendor_users:
            user_exists = True
            vendor_users[vendor_name].append(user)
        else:
            vendor_users[vendor_name] = []
            vendor_users[vendor_name].append(user)
        show_vendor_user_log(
            user, vendor_name, logger_name, connection_account, user_exists
        )
    return vendor_users


def validate_groups(connection_account: ConnectionAccount, token: str):
    prefetched_groups = connection_account.authentication.get('prefetch_group', [])
    groups = get_groups(token)
    prefetched_ids = [group.get('id') for group in prefetched_groups]
    group_ids = [group.get('id') for group in groups]
    settings_groups = connection_account.settings.get('groups', [])
    if prefetched_ids != group_ids:
        updated_groups = [
            _map_group_options(group)
            for group in groups
            if group.get('id') in settings_groups
        ]
        connection_account.settings['groups'] = [
            group.get('id') for group in updated_groups
        ]
        connection_account.authentication['prefetch_group'] = [
            _map_group_options(group) for group in groups
        ]
        connection_account.save()


def _map_group_options(group: dict) -> dict:
    return {'id': group.get('id'), 'value': {'name': group.get('displayName')}}


def validate_scopes_for_devices(connection_account, vendor_scopes):
    scopes = connection_account.authentication.get('scope', '')
    return vendor_scopes in scopes

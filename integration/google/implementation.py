import logging
from typing import Dict, List, Tuple, Union

from objects.system_types import ACCOUNT, USER, resolve_laika_object_type
from vendor.models import VendorCandidate

from ..account import get_integration_laika_objects, integrate_account
from ..discovery import (
    create_vendor_discovery_alert,
    exclude_existing_vendor_candidates,
    get_discovery_status_for_new_vendor_candidate,
    get_vendor_if_it_exists,
    validate_scopes_for_vendor_candidates,
)
from ..exceptions import ConfigurationError, ConnectionAlreadyExists
from ..integration_utils.google_utils import map_users_response
from ..integration_utils.vendor_users import create_sso_users, show_vendor_user_log
from ..models import ConnectionAccount
from ..store import Mapper, update_laika_objects
from ..types import FieldOptionsResponseType, GoogleOrganizationsType
from .constants import (
    DEFAULT_ORG_UNIT,
    GOOGLE_WORKSPACE_SYSTEM,
    INSUFFICIENT_ADMINISTRATOR_PERMISSIONS,
    ROLE_SCOPE,
    VENDOR_SCOPES,
)
from .rest_client import (
    create_access_token,
    create_refresh_token,
    get_organizations,
    get_role_assigment,
    get_roles,
    get_tokens,
    get_users,
)

N_RECORDS = get_integration_laika_objects(GOOGLE_WORKSPACE_SYSTEM)


logger_name = __name__

logger = logging.getLogger(__name__)


def perform_refresh_token(connection_account: ConnectionAccount):
    refresh_token = connection_account.authentication['refresh_token']
    access_token = create_access_token(refresh_token)
    if not access_token:
        logger.warning(
            f'Error refreshing token for {GOOGLE_WORKSPACE_SYSTEM} '
            f'connection account {connection_account.id}'
        )


def map_user_response_to_laika_object(user, connection_name):
    return map_users_response(user, connection_name, GOOGLE_WORKSPACE_SYSTEM)


def validate_is_admin_user(connection_account):
    with connection_account.connection_error(
        error_code=INSUFFICIENT_ADMINISTRATOR_PERMISSIONS
    ):
        refresh_token = connection_account.authentication['refresh_token']
        access_token = create_access_token(refresh_token)
        get_organizations(access_token)


def callback(code, redirect_uri, connection_account):
    if not code:
        raise ConfigurationError.denial_of_consent()

    response = create_refresh_token(code, redirect_uri)
    organization = connection_account.organization
    connection_account.authentication = response
    validate_is_admin_user(connection_account)
    resolve_laika_object_type(organization, USER)
    resolve_laika_object_type(organization, ACCOUNT)
    connection_account.save()
    return connection_account


def run(connection_account: ConnectionAccount):
    with connection_account.connection_attempt():
        integrate_users(connection_account)
        if validate_scopes_for_vendor_candidates(connection_account, VENDOR_SCOPES):
            new_vendors = integrate_vendor_candidates(connection_account)
            create_vendor_discovery_alert(connection_account, new_vendors)
        integrate_account(connection_account, GOOGLE_WORKSPACE_SYSTEM, N_RECORDS)


def get_vendor_names_and_vendor_users(connection_account: ConnectionAccount):
    refresh_token = connection_account.authentication['refresh_token']
    access_token = create_access_token(refresh_token)
    users = get_users(access_token)
    vendor_names = set()
    vendor_users: dict = {}
    for user in users:
        tokens = get_tokens(user['id'], access_token)
        for token in tokens.get('items', []):
            vendor_name = token['displayText']
            vendor_names.add(vendor_name)
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
    return vendor_names, vendor_users


def integrate_vendor_candidates(connection_account: ConnectionAccount):
    logger.info(
        'Integrating vendor candidates for Google - '
        f'Connection account {connection_account.id}'
    )
    vendor_names, vendor_users = get_vendor_names_and_vendor_users(connection_account)
    organization = connection_account.organization
    vendor_candidates = []
    vendor_candidate_names = exclude_existing_vendor_candidates(
        organization, vendor_names
    )
    logger.info(
        'Creating Google Workspace SSO Users - '
        f'Connection account {connection_account.id}'
    )
    create_sso_users(connection_account, vendor_users)
    for vendor_candidate_name in vendor_candidate_names:
        vendor = get_vendor_if_it_exists(vendor_candidate_name)
        status = get_discovery_status_for_new_vendor_candidate(organization, vendor)
        vendor_candidate = VendorCandidate(
            name=vendor_candidate_name,
            organization=organization,
            vendor=vendor,
            status=status,
            number_of_users=len(vendor_users.get(vendor_candidate_name)),
        )
        vendor_candidates.append(vendor_candidate)
    N_RECORDS["vendor_candidate"] = len(vendor_candidates)
    return VendorCandidate.objects.bulk_create(vendor_candidates)


def _get_customer_id_from_users(users: list) -> Union[str, None]:
    return users[0].get('customerId') if users else None


def integrate_users(connection_account: ConnectionAccount):
    refresh_token = connection_account.authentication['refresh_token']
    access_token = create_access_token(refresh_token)
    users = get_all_users(
        access_token=access_token, connection_account=connection_account
    )
    connection_account.authentication['customer_id'] = _get_customer_id_from_users(
        users
    )
    connection_account.save()
    raise_if_duplicate(connection_account)
    user_mapper = Mapper(
        map_function=map_user_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=USER,
    )
    if connection_account.settings:
        path = connection_account.settings.get('orgUnitPath')
        users = [user for user in users if path in user['orgUnitPath']]
    update_laika_objects(connection_account, user_mapper, users)


def raise_if_duplicate(connection_account: ConnectionAccount):
    customer_id = connection_account.authentication['customer_id']
    exists = (
        ConnectionAccount.objects.actives(
            authentication__customer_id=customer_id,
            organization=connection_account.organization,
        )
        .exclude(id=connection_account.id)
        .exists()
    )
    if exists:
        raise ConnectionAlreadyExists()


def org_list(
    refresh_token: str, connection_account: ConnectionAccount
) -> Tuple[list, dict]:
    access_token = create_access_token(refresh_token)
    response, error = get_organizations(access_token)
    organizations = [] if bool(error) else [DEFAULT_ORG_UNIT]
    for org in response:
        organizations.append({'id': org['orgUnitPath'], 'value': {'name': org['name']}})
    return organizations, error


def get_custom_field_options(
    field_name: str, connection_account: ConnectionAccount
) -> FieldOptionsResponseType:
    refresh_token = connection_account.authentication['refresh_token']
    if field_name != 'organization':
        raise NotImplementedError('Not implemented')
    organizations, _ = org_list(refresh_token, connection_account)
    return FieldOptionsResponseType(options=organizations)


def get_google_organizations(
    connection_account: ConnectionAccount,
) -> GoogleOrganizationsType:
    refresh_token = connection_account.authentication.get('refresh_token')
    organizations, error = (
        org_list(refresh_token, connection_account) if refresh_token else ([], {})
    )
    return GoogleOrganizationsType(options=organizations, error=error)


def get_all_users(
    access_token: str,
    connection_account: ConnectionAccount,
) -> List:
    users = get_users(auth_token=access_token)
    if ROLE_SCOPE not in connection_account.authentication.get('scope', {}):
        return users
    role_assigment_list = get_role_assigment(access_token)
    roles_list = get_roles(access_token)
    all_users = []
    for user in users:
        user_id = user.get('id')
        user_roles = _get_user_roles(
            user_id=user_id, roles=roles_list, roles_assigment=role_assigment_list
        )
        user['roles'] = _roles_array_to_object_string(user_roles)
        all_users.append(user)

    return all_users


def _get_user_roles(user_id: str, roles: Dict, roles_assigment: Dict) -> List:
    return (
        [roles[role_id] for role_id in roles_assigment[user_id] if role_id in roles]
        if user_id in roles_assigment
        else []
    )


def _roles_array_to_object_string(roles: List) -> str:
    return ', '.join(roles)

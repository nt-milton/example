import logging
import re

from cryptography.fernet import InvalidToken

from integration.store import Mapper, update_laika_objects
from objects.system_types import DEVICE, Device, resolve_laika_object_type

from ..account import get_integration_laika_objects, integrate_account
from ..encryption_utils import decrypt_value, encrypt_value
from ..exceptions import ConfigurationError, ConnectionAlreadyExists
from ..models import ConnectionAccount
from .constants import (
    INSUFFICIENT_PERMISSIONS,
    INVALID_CREDENTIALS,
    INVALID_SUBDOMAIN,
    PRIVILEGES,
)
from .rest_client import (
    get_access_token,
    get_auth_info,
    get_buildings,
    get_departments,
    get_devices,
)
from .utils import (
    IN_INVENTORY,
    ISSUED,
    MOBILE,
    NA,
    SUB_DOMAIN_REGEX,
    VALID_DOMAIN_REGEX,
    extract_price,
    format_location,
    get_computer_encryption_status,
    get_device_type,
    get_mobile_encryption_status,
)

logger = logging.getLogger(__name__)

JAMF_SYSTEM = 'Jamf'
N_RECORDS = get_integration_laika_objects(JAMF_SYSTEM)


def build_mapper(departments, buildings):
    def map_devices_to_laika_object(device, connection_name):
        if device.device_type == 'computer':
            return map_computers(device, connection_name, departments, buildings)
        elif device.device_type == 'mobile':
            return map_mobile_devices(device, connection_name, departments, buildings)

    return map_devices_to_laika_object


def map_computers(device, connection_name, departments, buildings):
    lo_device = Device()
    lo_device.id = device.device['id']
    lo_device.name = device.device['general']['name']
    device_model = device.device['hardware']['model']
    model = device_model.split() if device_model else None
    lo_device.device_type = get_device_type(model)
    lo_device.company_issued = True
    lo_device.serial_number = device.device['hardware']['serialNumber']
    lo_device.model = device_model
    lo_device.brand = device.device['hardware']['make']
    lo_device.operating_system = device.device['operatingSystem']['name']
    lo_device.os_version = device.device['operatingSystem']['version']
    location = device.device['userAndLocation']
    lo_device.location = format_location(
        department=departments.get(location['departmentId'], ''),
        building=buildings.get(location['buildingId'], ''),
        room=location['room'] if location['room'] else '',
    )
    lo_device.owner = device.device['userAndLocation']['username']
    lo_device.issuance_status = NA
    lo_device.anti_virus_status = NA
    encryption_details = device.device['diskEncryption'][
        'bootPartitionEncryptionDetails'
    ]
    lo_device.encryption_status = get_computer_encryption_status(encryption_details)
    lo_device.purchased_on = device.device['purchasing']['poDate']
    lo_device.cost = extract_price(device.device['purchasing']['purchasePrice'])
    lo_device.note = None
    lo_device.source_system = JAMF_SYSTEM
    lo_device.connection_name = connection_name
    return lo_device.data()


def map_mobile_devices(device, connection_name, departments, buildings):
    lo_device = Device()
    lo_device.id = device.device['id']
    lo_device.name = device.device['name']
    lo_device.device_type = MOBILE
    lo_device.company_issued = device.device['deviceOwnershipLevel'] == 'Institutional'
    lo_device.serial_number = device.device['serialNumber']
    device_type = device.device['type']
    lo_device.model = None
    lo_device.brand = 'Apple' if device_type == 'ios' else 'Other'
    lo_device.operating_system = device_type
    lo_device.os_version = device.device['osVersion']
    location = device.device['location']
    lo_device.location = format_location(
        department=departments.get(location['departmentId'], ''),
        building=buildings.get(location['buildingId'], ''),
        room=location['room'] if location['room'] else '',
    )
    lo_device.owner = location['username']
    lo_device.issuance_status = ISSUED if device.device['managed'] else IN_INVENTORY
    lo_device.anti_virus_status = NA
    lo_device.encryption_status = NA
    lo_device.purchased_on = None
    lo_device.cost = 0
    if device_type != 'unknown':
        lo_device.model = device.device.get('ios', {}).get('model', '')
        lo_device.encryption_status = get_mobile_encryption_status(
            device.device['ios']['security']
        )
        lo_device.purchased_on = device.device['ios']['purchasing']['poDate']
        lo_device.cost = extract_price(
            device.device['ios']['purchasing']['purchasePrice']
        )
    lo_device.note = None
    lo_device.source_system = JAMF_SYSTEM
    lo_device.connection_name = connection_name
    return lo_device.data()


def encrypt_password_if_not_encrypted(connection_account):
    credentials = connection_account.configuration_state['credentials']
    password = credentials['password']
    try:
        decrypt_value(password)
    except InvalidToken:
        password = credentials.get('password')
        encrypted_password = encrypt_value(password)
        credentials['password'] = encrypted_password
        connection_account.save()


def connect(connection_account: ConnectionAccount):
    if 'credentials' in connection_account.configuration_state:
        credentials = connection_account.configuration_state['credentials']
        with connection_account.connection_error(error_code=INVALID_SUBDOMAIN):
            valid_subdomain = get_valid_domain(credentials['subdomain'])
        credentials['subdomain'] = valid_subdomain
        encrypt_password_if_not_encrypted(connection_account)
        with connection_account.connection_error(error_code=INVALID_CREDENTIALS):
            token = validate_credentials(connection_account)
        with connection_account.connection_error(
            error_code=INSUFFICIENT_PERMISSIONS, keep_exception_error=True
        ):
            get_access_level_info(connection_account, token)
        organization = connection_account.organization
        resolve_laika_object_type(organization, DEVICE)


def run(connection_account: ConnectionAccount):
    with connection_account.connection_attempt():
        raise_if_duplicate(connection_account)
        access_token = validate_credentials(connection_account)
        integrate_devices(connection_account, access_token)
        integrate_account(connection_account, JAMF_SYSTEM, N_RECORDS)


def integrate_devices(connection_account: ConnectionAccount, api_key: str):
    credentials = connection_account.configuration_state.get('credentials', {})
    subdomain = credentials.get('subdomain', '')
    buildings = get_buildings(api_key, subdomain)
    departments = get_departments(api_key, subdomain)
    device_mapper = Mapper(
        map_function=build_mapper(departments, buildings),
        keys=['Id', 'Serial Number', 'Device Type'],
        laika_object_spec=DEVICE,
    )
    devices = get_devices(api_key, subdomain)
    update_laika_objects(connection_account, device_mapper, devices)


def raise_if_duplicate(connection_account: ConnectionAccount):
    credential = connection_account.configuration_state.get('credentials', {})
    username = credential.get('username', {})
    exists = (
        ConnectionAccount.objects.actives(
            configuration_state__credentials__username=username,
            organization=connection_account.organization,
        )
        .exclude(id=connection_account.id)
        .exists()
    )
    if exists:
        raise ConnectionAlreadyExists()


def validate_credentials(connection_account: ConnectionAccount):
    credential = connection_account.configuration_state.get('credentials', {})
    username = credential.get('username', {})
    encrypted_password = credential.get('password', {})
    decrypted_password = decrypt_value(encrypted_password)
    return get_access_token(credential, username, decrypted_password)


def get_valid_domain(sub_domain: str) -> str:
    if re.match(VALID_DOMAIN_REGEX, sub_domain):
        return sub_domain

    invalid_subdomain = re.search(SUB_DOMAIN_REGEX, sub_domain)

    if invalid_subdomain:
        matched_domain = invalid_subdomain.string[
            invalid_subdomain.start() : invalid_subdomain.end()
        ]
        return matched_domain.split('.')[0]
    else:
        error = {'message': 'subdomain does not match with the valid format'}
        raise ConfigurationError.bad_client_credentials(error)


def get_access_level_info(connection_account: ConnectionAccount, token):
    credential = connection_account.configuration_state.get('credentials', {})
    access_info = get_auth_info(credential, token)
    account_data: dict = access_info.get('account', {})
    privilege_set = account_data.get('privilegeSet')
    if privilege_set not in PRIVILEGES:
        error_message = dict(
            usernam=account_data.get('username'),
            accessLevel=account_data.get('accessLevel'),
            privilegeSet=account_data.get('privilegeSet'),
            message='The user does not have admin or audit roles',
        )
        raise ConfigurationError.insufficient_permission(response=error_message)

import typing

from integration.integration_utils.constants import NOT_APPLICABLE
from integration.integration_utils.microsoft_utils import GLOBAL_ADMIN, get_device_type
from objects.system_types import Device, User


def map_users_response(response, connection_name, source_system):
    user = response.user
    groups = [group for group in response.groups]
    organization_name = response.organization[0]['displayName']
    roles = [role for role in response.roles]
    user_id = user.get('id')
    lo_user = User()
    lo_user.id = user_id
    lo_user.first_name = user.get('givenName')
    lo_user.last_name = user.get('surname')
    lo_user.email = user.get('mail')
    lo_user.title = user.get('jobTitle', '')
    lo_user.is_admin = GLOBAL_ADMIN in roles
    lo_user.mfa_enabled = ''
    lo_user.roles = ', '.join(sorted(roles))
    lo_user.mfa_enforced = ''
    lo_user.organization_name = organization_name
    lo_user.groups = ', '.join(sorted(groups))
    lo_user.connection_name = connection_name
    lo_user.source_system = source_system
    return lo_user.data()


@typing.no_type_check
def map_devices_response(device: dict, connection_name: str, source_system: str):
    lo_device = Device()
    owners: list[str] = [
        owner.get('displayName') for owner in device.get('registeredOwners', [])
    ]
    device_name: str = device.get('displayName', '')
    lo_device.id = device['deviceId']
    lo_device.name = device_name
    lo_device.device_type = get_device_type(device_name)
    lo_device.company_issued = (
        True if device['deviceOwnership'] == 'corporate' else False
    )
    lo_device.serial_number = NOT_APPLICABLE
    lo_device.model = device['model']
    lo_device.brand = device['manufacturer']
    lo_device.operating_system = device['operatingSystem']
    lo_device.os_version = device['operatingSystemVersion']
    lo_device.location = device['trustType']
    lo_device.owner = ', '.join(sorted(owners))
    lo_device.issuance_status = NOT_APPLICABLE
    lo_device.anti_virus_status = NOT_APPLICABLE
    lo_device.encryption_status = NOT_APPLICABLE
    lo_device.purchased_on = None
    lo_device.cost = None
    lo_device.note = NOT_APPLICABLE
    lo_device.source_system = source_system
    lo_device.connection_name = connection_name
    return lo_device.data()

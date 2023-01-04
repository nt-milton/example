import typing

from integration.integration_utils.constants import NOT_APPLICABLE
from integration.integration_utils.microsoft_utils import get_device_type
from objects.system_types import Device


@typing.no_type_check
def map_managed_devices_response(
    device: dict, connection_name: str, source_system: str
):
    device_name: str = device.get('deviceName', '')
    lo_device = Device()
    lo_device.id = device['id']
    lo_device.name = device['deviceName']
    lo_device.device_type = get_device_type(device_name)
    lo_device.company_issued = (
        True if device['managedDeviceOwnerType'] == 'company' else False
    )
    lo_device.serial_number = device['serialNumber']
    lo_device.model = device['model']
    lo_device.brand = device['manufacturer']
    lo_device.operating_system = device['operatingSystem']
    lo_device.os_version = device['osVersion']
    lo_device.location = NOT_APPLICABLE
    lo_device.owner = device['userPrincipalName']
    lo_device.issuance_status = NOT_APPLICABLE
    lo_device.anti_virus_status = NOT_APPLICABLE
    lo_device.encryption_status = (
        'Encrypted' if device['isEncrypted'] is True else 'Not encrypted'
    )
    lo_device.purchased_on = None
    lo_device.cost = None
    lo_device.note = device['notes']
    lo_device.source_system = source_system
    lo_device.connection_name = connection_name
    return lo_device.data()

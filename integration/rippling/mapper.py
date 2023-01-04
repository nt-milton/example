from objects.system_types import Device, User

from .constants import DESKTOP, LAPTOP, MOBILE, NA, OTHERS, PRINTER

RIPPLING_SYSTEM = 'Rippling'


device_type = {
    'PRINTER': PRINTER,
    'DESKTOP': DESKTOP,
    'MOBILE_PHONE': MOBILE,
    'LAPTOP': LAPTOP,
}


def build_mapper(company):
    def map_user_response_to_laika_object(user, connection_name):
        lo_user = User()
        lo_user.id = user.get('id', '')
        lo_user.first_name = user.get('firstName', '')
        lo_user.last_name = user.get('lastName', '')
        lo_user.email = user.get('workEmail', '')
        lo_user.title = user.get('title', '')
        lo_user.organization_name = company.get('legalName', '')
        lo_user.source_system = RIPPLING_SYSTEM
        lo_user.connection_name = connection_name
        return lo_user.data()

    return map_user_response_to_laika_object


def map_device_response_to_laika_object(device, connection_name):
    lo_device = Device()
    lo_device.id = device.get('Serial number', '')
    lo_device.serial_number = device.get('Serial number', '')
    lo_device.owner = device.get('Full name', '')
    lo_device.location = device.get('Location', '')
    lo_device.brand = device.get('Manufacturer', '')
    lo_device.model = device.get('SKU', '')
    lo_device.device_type = device_type.get(device.get('Hardware type', ''), OTHERS)
    lo_device.company_issued = device.get('Is leased', '')
    lo_device.issuance_status = NA
    lo_device.anti_virus_status = NA
    lo_device.encryption_status = NA
    lo_device.source_system = RIPPLING_SYSTEM
    lo_device.connection_name = connection_name
    return lo_device.data()

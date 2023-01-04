import json
from pathlib import Path

import pytest

from integration.jamf.implementation import JAMF_SYSTEM, build_mapper
from integration.jamf.rest_client import RawDevices
from integration.jamf.utils import ENCRYPTED, LAPTOP, NA, extract_price

PARENT_PATH = Path(__file__).parent
LOCATION = 'Remote, 301 4th Ave. S\r\nSuite 1075'
EPIC_NAME = 'EPIC TEST'
USERNAME = 'Dev Team'
DEVELOPMENT = 'In Development'
COMPLETED = 'Completed'


@pytest.fixture
def device_payload():
    path = PARENT_PATH / 'raw_devices_response.json'
    return json.loads(open(path, 'r').read())


@pytest.fixture
def map_function():
    departments = {'1': 'Department of Redundancy Department'}
    buildings = {'11': 'Hong Kong', '19': 'Minneapolis', '7': 'Remote', '4': 'US Field'}
    return build_mapper(departments, buildings)


def test_laika_object_mapping_device(device_payload, map_function):
    alias = 'testing_account'
    raw_device = device_payload[2]
    result = map_function(RawDevices(device_type='computer', device=raw_device), alias)
    expected = {
        'Id': raw_device['id'],
        'Name': raw_device['general']['name'],
        'Device Type': LAPTOP,
        'Company Issued': True,
        'Serial Number': raw_device['hardware']['serialNumber'],
        'Model': raw_device['hardware']['model'],
        'Brand': raw_device['hardware']['make'],
        'Operating System': raw_device['operatingSystem']['name'],
        'OS Version': raw_device['operatingSystem']['version'],
        'Location': LOCATION,
        'Owner': raw_device['userAndLocation']['username'],
        'Issuance Status': NA,
        'Anti Virus Status': NA,
        'Encryption Status': ENCRYPTED,
        'Purchased On': raw_device['purchasing']['leaseDate'],
        'Cost': extract_price(raw_device['purchasing']['purchasePrice']),
        'Note': None,
        'Source System': JAMF_SYSTEM,
        'Connection Name': alias,
    }
    assert result == expected

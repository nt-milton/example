import pytest

from integration.discovery import (
    get_discovery_status_for_new_vendor_candidate,
    get_vendor_if_it_exists,
)
from integration.tests.factory import _create_vendor, create_connection_account
from vendor.models import DISCOVERY_STATUS_NEW


@pytest.fixture
def connection_account():
    return create_connection_account('test')


@pytest.mark.functional
def test_vendor_if_exists():
    vendor = _create_vendor('Test')
    assert vendor == get_vendor_if_it_exists('Test')


@pytest.mark.functional
def test_discovery_status_for_new_vendor_candidate(connection_account):
    vendor = _create_vendor('Test')
    status = get_discovery_status_for_new_vendor_candidate(
        connection_account.organization, vendor
    )
    assert status == DISCOVERY_STATUS_NEW

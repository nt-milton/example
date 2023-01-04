import pytest

from vendor.models import OrganizationVendor
from vendor.tests.factory import create_organization_vendor, create_vendor
from vendor.utils import launchpad_mapper


@pytest.fixture(name="vendor")
def fixture_vendor(graphql_organization):
    test_vendor = create_vendor(
        name='Control Vendor', description='For testing purposes'
    )
    return create_organization_vendor(
        vendor=test_vendor, organization=graphql_organization
    )


@pytest.mark.django_db
def test_vendor_mapper(vendor, graphql_organization):
    vendors = launchpad_mapper(OrganizationVendor, graphql_organization.id)
    vendor_context = vendors[0]

    assert vendor_context.name == vendor.vendor.name
    assert vendor_context.description.strip() == vendor.vendor.description.strip()

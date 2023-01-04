from datetime import datetime

from access_review.models import AccessReviewVendorPreference
from integration.tests.factory import create_connection_account, create_integration
from objects.system_types import SERVICE_ACCOUNT, USER, resolve_laika_object_type
from objects.tests.factory import create_laika_object
from organization.models import Organization
from organization.tests.factory import create_organization
from vendor.models import (
    DISCOVERY_STATUS_PENDING,
    OrganizationVendor,
    Vendor,
    VendorCandidate,
)


def create_vendor_candidate(organization=None, name=None, status=None, vendor=None):
    if organization is None:
        organization = create_organization()
    if name is None:
        name = 'vendor candidate'
    if status is None:
        status = DISCOVERY_STATUS_PENDING
    vendor_candidate = VendorCandidate.objects.create(
        name=name, status=status, organization=organization, vendor=vendor
    )
    return vendor_candidate


def create_vendor(name=None, website=None, description=None, is_public=None):
    if name is None:
        name = 'vendor'
    if website is None:
        website = 'https://localhost/'
    if description is None:
        description = 'description test'
    if is_public is None:
        is_public = True
    vendor = Vendor.objects.create(
        name=name, website=website, description=description, is_public=is_public
    )
    return vendor


def create_organization_vendor(
    organization: Organization, vendor: Vendor, risk_rating: str = ''
) -> OrganizationVendor:
    return OrganizationVendor.objects.create(
        organization=organization, vendor=vendor, risk_rating=risk_rating
    )


def create_service_accounts_for_testing(organization, user, vendor):
    connection_account = create_connection_account(
        None,
        alias='Connection Account',
        organization=organization,
        created_by=user,
        integration=create_integration(None, vendor=vendor),
    )
    user_type = resolve_laika_object_type(organization, USER)
    create_laika_object(
        user_type,
        connection_account,
        {
            'First Name': 'lo',
            'Last Name': 'user',
            'Groups': 'testing',
            'Roles': 'testing',
            'Email': 'user@heylaika.com',
        },
    )
    create_laika_object(
        user_type,
        connection_account,
        {
            'First Name': 'lo',
            'Last Name': 'user 2',
            'Groups': 'testing',
            'Roles': 'testing',
            'Email': 'user@heylaika.com',
        },
    )
    deleted_user = create_laika_object(
        user_type,
        connection_account,
        {
            'First Name': 'deleted',
            'Last Name': 'user',
            'Groups': 'deleted',
            'Roles': 'deleted',
            'Email': 'deleted@heylaika.com',
        },
    )
    deleted_user.deleted_at = datetime.now()
    deleted_user.save()
    service_account_type = resolve_laika_object_type(organization, SERVICE_ACCOUNT)
    create_laika_object(
        service_account_type,
        connection_account,
        {
            'Display Name': 'lo_service_account',
            'Email': 'user@heylaika.com',
            'Roles': 'testing',
        },
    )
    create_laika_object(
        service_account_type,
        connection_account,
        {
            'Display Name': 'lo_service_account_2',
            'Email': 'user@heylaika.com',
            'Roles': 'testing',
        },
    )
    deleted_service_account = create_laika_object(
        service_account_type,
        connection_account,
        {
            'Display Name': 'lo_service_account_deleted',
            'Email': 'deleted@heylaika.com',
            'Roles': 'deleted',
        },
    )
    deleted_service_account.deleted_at = datetime.now()
    deleted_service_account.save()
    AccessReviewVendorPreference.objects.create(
        organization_vendor=create_organization_vendor(organization, vendor),
        in_scope=True,
    )

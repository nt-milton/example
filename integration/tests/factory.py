from unittest import mock

import pytest
from django.core.files import File
from django.test import RequestFactory

from integration import signals
from integration.models import (
    OTHER,
    ConnectionAccount,
    ConnectionAccountDebugAction,
    ErrorCatalogue,
    Integration,
    IntegrationAlert,
)
from objects.models import LaikaObject
from organization.tests import create_organization
from user.constants import ACTIVE
from user.tests import create_user


def create_connection_account(
    vendor_name,
    alias=None,
    organization=None,
    integration=None,
    integration_metadata=None,
    created_by=None,
    configuration_state=None,
    authentication=None,
    vendor=None,
    **kwargs,
):
    if not alias:
        alias = f'{vendor_name} test'
    if not organization:
        organization = create_organization(name='organization', state=ACTIVE)
        organization.compliance_architect_user = create_user(
            organization, email='heylaika+ca@heylaika.com'
        )
        organization.customer_success_manager_user = create_user(
            organization, email='heylaika+csm@heylaika.com'
        )
        organization.save()
    if not integration:
        integration = create_integration(
            vendor_name=vendor_name, vendor=vendor, metadata=integration_metadata
        )
    if not configuration_state:
        configuration_state = {}
    if not created_by:
        created_by = create_user(organization, email='heylaika@heylaika.com')
    if not authentication:
        authentication = {}
    signals.post_save.disconnect(sender=ConnectionAccount)
    connection_account = ConnectionAccount.objects.create(
        alias=alias,
        integration=integration,
        organization=organization,
        created_by=created_by,
        configuration_state=configuration_state,
        authentication=authentication,
        **kwargs,
    )
    return connection_account


def _create_vendor(vendor_name):
    from vendor.models import Vendor

    vendor = Vendor.objects.create(name=vendor_name)
    file_mock = mock.MagicMock(spec=File)
    file_mock.name = 'vendor_logo.png'
    vendor.logo = file_mock
    return vendor


def create_integration(vendor_name, vendor=None, metadata=None, category=OTHER):
    if not vendor:
        vendor = _create_vendor(vendor_name)
    if not metadata:
        metadata = {
            'configuration_fields': ['test_field'],
            'param_redirect_uri': 'https://redirect.uri.com',
        }
    file_mock = mock.MagicMock(spec=File)
    file_mock.name = 'email_logo.png'
    integration = Integration.objects.create(
        vendor=vendor,
        description='Dummy Integration',
        metadata=metadata,
        category=category,
    )
    integration.email_logo = file_mock
    return integration


def create_request_for_callback(connection_account):
    vendor_name = connection_account.integration.vendor.name
    return RequestFactory().get(
        f'https://localhost:8000/integration/{vendor_name}/callback'
        f'?code=code&state={connection_account.control}'
    )


def create_error_catalogue(code, error='', description='', send_email=True):
    error_catalogue, _ = ErrorCatalogue.objects.get_or_create(
        code=code, error=error, send_email=send_email, description=description
    )
    return error_catalogue


def create_integration_alert(integration, error, wizard_error_code):
    return IntegrationAlert.objects.get_or_create(
        integration=integration, error=error, wizard_error_code=wizard_error_code
    )


def create_debug_status(name='Pending Laika Action', status='LAIKA_ACTION_REQUIRED'):
    return ConnectionAccountDebugAction.objects.create(name=name, status=status)


@pytest.mark.django_db
def get_db_number_of_records(connection_account):
    n_account_laika_object = LaikaObject.objects.get(
        connection_account=connection_account, object_type__type_name='account'
    ).data['Number of Records']
    return n_account_laika_object

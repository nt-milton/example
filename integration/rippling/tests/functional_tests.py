import pytest

from integration import rippling
from integration.account import set_connection_account_number_of_records
from integration.error_codes import INSUFFICIENT_PERMISSIONS
from integration.exceptions import ConfigurationError
from integration.models import PENDING
from integration.rippling.implementation import N_RECORDS
from integration.rippling.tests.fake_api import (
    fake_rippling_api,
    fake_rippling_api_without_permissions,
)
from integration.tests import create_connection_account, create_request_for_callback
from integration.tests.factory import get_db_number_of_records
from integration.views import oauth_callback
from objects.models import LaikaObjectType
from objects.system_types import ACCOUNT, USER
from user.models import DISCOVERY_STATE_NEW, User

RIPPLING_SYSTEM = 'rippling'


@pytest.fixture
def connection_account():
    with fake_rippling_api():
        yield rippling_connection_account()


@pytest.fixture
def connection_account_without_permissions():
    with fake_rippling_api_without_permissions():
        yield rippling_connection_account()


@pytest.fixture
def connection_account_with_domains():
    with fake_rippling_api():
        yield rippling_connection_account_with_domains()


@pytest.mark.functional
def test_rippling_integration_callback(connection_account):
    request = create_request_for_callback(connection_account)
    oauth_callback(request, RIPPLING_SYSTEM)
    assert connection_account.status == PENDING
    assert LaikaObjectType.objects.get(
        organization=connection_account.organization, type_name=USER.type
    )
    assert LaikaObjectType.objects.get(
        organization=connection_account.organization, type_name=ACCOUNT.type
    )
    # assert LaikaObjectType.objects.get(
    #     organization=connection_account.organization,
    #     type_name=DEVICE.type
    # )


@pytest.mark.functional
def test_rippling_integrate_account_number_of_records(
    connection_account, create_permission_groups
):
    rippling.run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


@pytest.mark.functional
def test_rippling_integrate_with_domain_filters(
    connection_account_with_domains, create_permission_groups
):
    rippling.run(connection_account_with_domains)

    assert User.objects.filter(
        email='wilburn.schulist9@laika.com', discovery_state=DISCOVERY_STATE_NEW
    ).exists()
    assert not User.objects.filter(
        email='danelle.witting10@laika2.com', discovery_state=DISCOVERY_STATE_NEW
    ).exists()


@pytest.mark.functional
def test_rippling_denial_of_consent_validation(connection_account):
    with pytest.raises(ConfigurationError):
        rippling.callback(None, 'test-rippling-callback', connection_account)


@pytest.mark.skip(
    reason="Blocked until Rippling's team provide a solution for this endpoint"
)
def test_rippling_insufficient_permissions(connection_account_without_permissions):
    with pytest.raises(ConfigurationError):
        rippling.run(connection_account_without_permissions)
        error_code = connection_account_without_permissions.error_code
        assert error_code == INSUFFICIENT_PERMISSIONS


def rippling_connection_account(**kwargs):
    connection_account = create_connection_account(
        'Rippling',
        authentication={
            "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9",
            "token_type": "bearer",
            "expires_in": 3600,
            "refresh_token": "0e8cfdf933e1a09765580e694f444c4f",
            "data": {},
        },
        **kwargs
    )
    return connection_account


def rippling_connection_account_with_domains(**kwargs):
    connection_account = create_connection_account(
        'Rippling',
        authentication={
            "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9",
            "token_type": "bearer",
            "expires_in": 3600,
            "refresh_token": "0e8cfdf933e1a09765580e694f444c4f",
            "data": {},
        },
        configuration_state={"validDomains": ['laika.com']},
        **kwargs
    )
    return connection_account

import pytest

from integration import asana
from integration.account import set_connection_account_number_of_records
from integration.asana.implementation import N_RECORDS, clean_up_projects
from integration.asana.tests.fake_api import (
    fake_asana_api,
    fake_failure_asana_api,
    fake_no_access_asana_api,
)
from integration.error_codes import EXPIRED_TOKEN
from integration.exceptions import ConfigurationError
from integration.models import PENDING
from integration.tests import create_connection_account, create_request_for_callback
from integration.tests.factory import get_db_number_of_records
from integration.views import oauth_callback
from objects.models import LaikaObjectType
from objects.system_types import ACCOUNT, CHANGE_REQUEST, USER

ASANA_SYSTEM = 'asana'


@pytest.fixture
def connection_account():
    with fake_asana_api():
        yield asana_connection_account()


@pytest.fixture
def failure_connection_account():
    with fake_failure_asana_api():
        yield asana_connection_account()


@pytest.fixture
def no_access_connection_account():
    with fake_no_access_asana_api():
        yield asana_connection_account()


@pytest.mark.functional
def test_asana_integration_callback(connection_account):
    request = create_request_for_callback(connection_account)
    oauth_callback(request, ASANA_SYSTEM)
    assert connection_account.status == PENDING
    assert LaikaObjectType.objects.get(
        organization=connection_account.organization, type_name=USER.type
    )
    assert LaikaObjectType.objects.get(
        organization=connection_account.organization, type_name=ACCOUNT.type
    )
    assert LaikaObjectType.objects.get(
        organization=connection_account.organization, type_name=CHANGE_REQUEST.type
    )


@pytest.mark.functional
def test_asana_integrate_account_number_of_records(connection_account):
    asana.run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


@pytest.mark.functional
def test_asana_denial_of_consent_validation(connection_account):
    with pytest.raises(ConfigurationError):
        asana.callback(None, 'test-asana-callback', connection_account)


@pytest.mark.functional
def test_get_custom_field_options(connection_account):
    get_project_options = asana.get_custom_field_options("project", connection_account)
    expected_project = {
        'id': '1153673585967972',
        'value': {
            'name': 'Artis LendingCompliance Readiness',
            'projectType': 'project',
            'workspaceName': 'heylaika.com',
        },
    }
    assert get_project_options.options[0] == expected_project


@pytest.mark.functional
def test_asana_integration_fail_with_expired_account(failure_connection_account):
    with pytest.raises(ConfigurationError):
        asana.run(failure_connection_account)
    assert failure_connection_account.error_code == EXPIRED_TOKEN
    assert (
        'The bearer token has expired'
        in failure_connection_account.result["error_response"]
    )


@pytest.mark.functional
def test_asana_outdated_projects(connection_account):
    deleted_project = '1154257823496066'
    projects = connection_account.settings['projects']
    connection_account.settings['projects'] = [*projects, deleted_project]
    connection_account.save()
    assert deleted_project in connection_account.settings['projects']
    clean_up_projects(connection_account)
    assert deleted_project not in connection_account.settings['projects']


def asana_connection_account(**kwargs):
    connection_account = create_connection_account(
        'Asana',
        authentication={
            "access_token": (
                "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdXRob3Jpe"
                "mF0aW9uIjoxMTk5ODk3NzA0MTg2MjI2LCJzY29wZSI6ImRlZmF"
                "1bHQgaWRlbnRpdHkiLCJzdWIiOjExOTk4ODM5NzQ1MTYzODAsI"
                "mlhdCI6MTYxMjgyNTExOCwiZXhwIjoxNjEyODI4NzE4fQ.hUzN"
                "H8ZbAXkhE1VZQTN1zQe-qx0RSp9XpTVEzy9R2NM"
            ),
            "token_type": "bearer",
            "expires_in": 3600,
            "data": {
                "id": 1199883974516380,
                "gid": "1199883974516380",
                "name": "development account",
                "email": "dev@heylaika.com",
            },
            "refresh_token": "1/1199883974516380:0e8cfdf933e1a09765580e694f444c4f",
        },
        configuration_state={'settings': {'projects': ['1153259180336055']}},
        **kwargs
    )
    return connection_account

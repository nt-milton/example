from collections import namedtuple

import pytest
from httmock import HTTMock, response, urlmatch

from integration import github_apps
from integration.account import set_connection_account_number_of_records
from integration.encryption_utils import decrypt_value
from integration.error_codes import USER_INPUT_ERROR
from integration.exceptions import ConfigurationError
from integration.github_apps.implementation import N_RECORDS, run_by_lo_types
from integration.models import ConnectionAccount
from integration.tests.factory import create_error_catalogue, get_db_number_of_records
from objects.models import LaikaObject
from objects.system_types import PULL_REQUEST

HEYLAIKA = 'heylaika'


def _add_default_values_for_testing(connection_account: ConnectionAccount) -> None:
    connection_account.configuration_state = dict(
        organizations=[HEYLAIKA], credentials={'organization': HEYLAIKA}
    )
    connection_account.authentication['installation'] = {
        'login': HEYLAIKA,
        'installation_id': 111111,
    }


@pytest.mark.functional
def test_github_integration_connect_new_application(
    connection_account: ConnectionAccount,
):
    connection_account.configuration_state = dict(
        credentials={
            'organization': HEYLAIKA,
            'installationId': 111111,
        },
    )
    github_apps.connect(connection_account)
    new_connection_account = ConnectionAccount.objects.get(id=connection_account.id)
    installations = new_connection_account.authentication['installation']
    expected_installation_login = HEYLAIKA
    assert decrypt_value(installations.get('login')) == expected_installation_login


@pytest.mark.functional
def test_github_integration_connect_new_application_wrong_installation_id(
    connection_account: ConnectionAccount, caplog
):
    create_error_catalogue(USER_INPUT_ERROR)
    connection_account.configuration_state = dict(
        credentials={
            'organization': HEYLAIKA,
            'installationId': 112111,
        },
    )
    with pytest.raises(ConfigurationError):
        github_apps.connect(connection_account)

    assert f'Application {HEYLAIKA} not installed in Github account' in caplog.text


@pytest.mark.functional
def test_github_integration_create_laika_objects(connection_account: ConnectionAccount):
    _add_default_values_for_testing(connection_account)

    github_apps.run(connection_account)
    pull_requests = LaikaObject.objects.filter(
        object_type__type_name=PULL_REQUEST.type,
        data__Organization=HEYLAIKA,
        data__Repository='laika-app',
    )
    assert pull_requests.count() == 5

    def get_approvers():
        pull_request_info = namedtuple('PullRequestInfo', 'approvers')
        for pr in pull_requests:
            yield pull_request_info(pr.data['Approvers'])

    approver_info = get_approvers()
    assert next(approver_info).approvers == 'ronaldzuniga'
    assert next(approver_info).approvers == ''
    assert next(approver_info).approvers == 'jeffrey,otto'
    assert next(approver_info).approvers == ''
    assert next(approver_info).approvers == 'jeffrey'


@pytest.mark.functional
def test_github_run_by_lo_types_with_lo_type(connection_account: ConnectionAccount):
    _add_default_values_for_testing(connection_account)

    run_by_lo_types(connection_account, ['testing'])
    assert not LaikaObject.objects.filter(
        object_type__type_name=PULL_REQUEST.type
    ).exists()


@pytest.mark.functional
def test_github_run_by_lo_types_without_lo_types(connection_account: ConnectionAccount):
    _add_default_values_for_testing(connection_account)

    run_by_lo_types(connection_account, [])
    assert LaikaObject.objects.filter(object_type__type_name=PULL_REQUEST.type).exists()


@pytest.mark.functional
def test_github_integrate_account_number_of_records(
    connection_account: ConnectionAccount,
):
    _add_default_values_for_testing(connection_account)
    github_apps.run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


@pytest.fixture
def function_call_counting():
    return {'count': 0}


@pytest.mark.functional
def test_github_integration_throw_secondary_rate_limit(
    connection_account: ConnectionAccount, function_call_counting, caplog
):
    # https://docs.github.com/en/rest/overview/resources-in-the-rest-api#secondary-rate-limits
    error_message = (
        "You have exceeded a secondary rate limit and have "
        "been temporarily blocked from content "
        "creation. Please retry your request again later."
    )
    doc_url = (
        "https://docs.github.com/rest/overview/"
        "resources-in-the-rest-api#secondary-rate-limits"
    )
    _add_default_values_for_testing(connection_account)

    @urlmatch(netloc=r'api.github.com', path='/graphql')
    def response_with_secondary_rate_limit(url, request):
        request_body = request.body.decode('utf-8')
        if 'pullRequests' in request_body:
            function_call_counting['count'] = int(function_call_counting['count']) + 1
            if int(function_call_counting['count']) == 1:
                return response(
                    status_code=403,
                    content={'message': error_message, 'documentation_url': doc_url},
                )

    with HTTMock(response_with_secondary_rate_limit):
        github_apps.run(connection_account)

        assert connection_account.status == 'success'

    assert error_message in caplog.text


@pytest.mark.functional
def test_github_integration_throw_exception_pull_request_call(
    connection_account: ConnectionAccount, function_call_counting
):
    organizations = [
        {'login': 'LaikaTest', 'installation_id': 111111},
        {'login': 'LaikaTest2', 'installation_id': 222222},
    ]
    connection_account.authentication['installations'] = organizations

    @urlmatch(netloc=r'api.github.com', path='/graphql')
    def response_with_provider_server_error(url, request):
        request_body = request.body.decode('utf-8')
        if 'pullRequests' in request_body:
            function_call_counting['count'] = int(function_call_counting['count']) + 1
            if int(function_call_counting['count']) == 1:
                return response(
                    status_code=500, content={'message': 'Error on github side'}
                )

    with HTTMock(response_with_provider_server_error):
        with pytest.raises(ConfigurationError):
            github_apps.run(connection_account)

    assert connection_account.status == 'error'

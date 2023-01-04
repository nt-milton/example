import time
from unittest.mock import patch

import pytest

from integration import error_codes, github_apps
from integration.exceptions import ConfigurationError
from integration.github_apps import implementation
from integration.models import ConnectionAccount, ErrorCatalogue
from objects.models import LaikaObject
from objects.system_types import PULL_REQUEST, REPOSITORY

organization = {
    'login': 'heylaika',
    'access_token': 'ghs_FAKETOKEN1',
    'installation_id': 20867660,
}

# FAKE API
# laika-web and laika-app have 5 PR's each one
#   2 of then (for each repo) with updatedAt - 17 months
#   2 others with updatedAt - 5 months
#   1 with updatedAt today

# autobots-web has 6 PR's
#   2 of then (for each repo) with updatedAt - 17 months
#   2 others with updatedAt - 5 months
#   2 with updatedAt today
#
# autobots-app has 5 PR's
#   2 of then (for each repo) with updatedAt - 17 months
#   2 others with updatedAt - 5 months
#   1 with updatedAt today

# TEST:
# 1- First time run executes the last_successful_run is None
#   1.1- So all PRs are populated and anything will be deletedAt
# 2- Second time run execute the last_successful_run has the today date
# NOTE: for this second time the time_range was changed to be now six_months
#   2.1- So NOT new PRs are added
#   2.2- But based on fake_api for PRs, 2 PRs by repo will be soft deleted
#       because are out of date range


@pytest.mark.functional
def test_integrate_pull_request_with_last_run(connection_account: ConnectionAccount):
    connection_account.authentication['installation'] = organization
    connection_account.configuration_state = dict(
        credentials={'organization': organization.get('login')}
    )
    connection_account.save()
    # First time that executes, last_successful_run is None
    github_apps.run(connection_account)

    repo_names = (
        LaikaObject.objects.filter(
            object_type__type_name=REPOSITORY.type,
            connection_account=connection_account,
        )
        .order_by('data__Name')
        .values_list('data__Name')
    )

    repo_list = [repo_name[0] for repo_name in repo_names]
    assert 'laika-app' in repo_list
    assert 'laika-web' in repo_list
    assert len(repo_list) == 2

    # Second time that executes, last_successful_run has today date
    github_apps.run(connection_account)

    pull_requests_soft_deleted = (
        LaikaObject.objects.filter(
            object_type__type_name=PULL_REQUEST.type,
            connection_account=connection_account,
            deleted_at__isnull=False,  # Note: date when this was soft deleted
        )
        .order_by('data__Key')
        .values_list('data__Key')
    )
    pr_list = [pr[0] for pr in pull_requests_soft_deleted]
    # This PR's have in the updatedAt more than six months
    soft_deleted_pr = ['laika-web-3', 'laika-web-4', 'laika-app-3', 'laika-app-4']
    assert len(pr_list) == len(soft_deleted_pr)
    for pr in soft_deleted_pr:
        assert pr in pr_list


@pytest.mark.functional
def test_connect_without_organization(connection_account: ConnectionAccount, caplog):
    _create_error_in_catalogue()
    connection_account.configuration_state['credentials'] = {}
    connection_account.configuration_state['credentials']['organization'] = None

    with pytest.raises(ConfigurationError):
        github_apps.connect(connection_account)

    assert (
        f'Connection account {connection_account.id} - Organization is required.'
        in caplog.text
    )


@pytest.mark.functional
def test_run_without_organizations(connection_account: ConnectionAccount, caplog):
    _create_error_in_catalogue()
    connection_account.configuration_state['credentials'] = {}
    # Wizard
    connection_account.configuration_state['credentials']['organization'] = 'heylaika'

    # Configuration state - already added
    connection_account.configuration_state['organization'] = []

    with pytest.raises(ConfigurationError):
        github_apps.run(connection_account)

    assert 'No Github Apps installations found' in caplog.text


@pytest.mark.functional
def test_connect_github_application_is_not_installed_error(
    connection_account_bad_org: ConnectionAccount, caplog
):
    _create_error_in_catalogue()
    connection_account_bad_org.configuration_state['credentials'] = {}
    # Wizard
    connection_account_bad_org.configuration_state['credentials'][
        'organization'
    ] = 'no_installed_app'

    connection_account_bad_org.authentication['installations'] = organization

    with pytest.raises(ConfigurationError):
        github_apps.connect(connection_account_bad_org)

    assert (
        f'Connection account {connection_account_bad_org.id} - Application '
        'no_installed_app not installed in Github account'
        in caplog.text
    )


@pytest.mark.functional
def test_connect_github_personal_account_error(
    connection_account_bad_user: ConnectionAccount, caplog
):
    _create_error_in_catalogue()
    connection_account_bad_user.configuration_state['credentials'] = {}
    # Wizard
    connection_account_bad_user.configuration_state['credentials'][
        'organization'
    ] = 'personal_account'

    connection_account_bad_user.authentication['installations'] = organization

    with pytest.raises(ConfigurationError):
        github_apps.connect(connection_account_bad_user)

    assert (
        f'Connection account {connection_account_bad_user.id} - Application '
        'personal_account is a personal account'
        in caplog.text
    )


def _create_error_in_catalogue():
    object_error = {
        'code': error_codes.USER_INPUT_ERROR,
        'error': 'USER_INPUT_ERROR',
        'default_wizard_message': '<p>The user entered an invalid value</p>',
        'failure_reason_mail': 'The user entered an invalid value',
        'send_email': False,
        'description': 'The user entered an invalid value',
    }
    ErrorCatalogue.objects.create(**object_error)


REFRESH_FUNCTION = (
    'integration.github_apps.implementation._reload_access_tokens_by_apps'
)


@pytest.mark.functional
def test_expired_tokens(connection_account: ConnectionAccount):
    connection_account.authentication['installation'] = organization
    installations = implementation.get_installation(connection_account)
    with patch(REFRESH_FUNCTION) as mock:
        installations.fetch_token()
        mock.assert_called_once()


@pytest.mark.functional
def test_not_expired_tokens(connection_account: ConnectionAccount):
    authentication = connection_account.authentication
    authentication['installation'] = organization
    installations = implementation.get_installation(connection_account)
    five_sec_future = int(time.time()) + 5
    authentication[implementation.TOKEN_EXPIRATION] = five_sec_future
    with patch(REFRESH_FUNCTION) as mock:
        installations.fetch_token()
        mock.assert_not_called()

import pytest

from integration.github_apps.tests.fake_api import (
    fake_bad_org_api,
    fake_bad_user_api,
    fake_github_api,
)
from integration.log_utils import connection_log
from integration.tests import create_connection_account


@pytest.fixture
def connection_account():
    with fake_github_api():
        account = github_connection_account()
        with connection_log(account):
            yield account


@pytest.fixture
def connection_account_bad_org():
    with fake_bad_org_api():
        account = github_connection_account()
        with connection_log(account):
            yield account


@pytest.fixture
def connection_account_bad_user():
    with fake_bad_user_api():
        account = github_connection_account()
        with connection_log(account):
            yield account


def github_connection_account():
    return create_connection_account('GitHub')

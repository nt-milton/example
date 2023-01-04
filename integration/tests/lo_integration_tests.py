from datetime import datetime, timedelta

import pytest

from laika.constants import DAILY, WEEKLY
from objects.models import LaikaObject
from objects.system_types import ACCOUNT, CHANGE_REQUEST, REPOSITORY, USER
from user.constants import ONBOARDING

from ..asana.implementation import run as asana_run
from ..asana.tests.functional_tests import (
    connection_account as connection_account_asana,
)
from ..bitbucket.implementation import run as bitbucket_run
from ..bitbucket.tests.functional_tests import (
    connection_account as connection_account_bitbucket,
)
from ..exceptions import ConnectionAccountSyncing
from ..github.implementation import run as github_run
from ..github.tests.functional_tests import (
    connection_account as connection_account_github,
)
from ..gitlab.implementation import run as gitlab_run
from ..gitlab.tests.functional_tests import (
    connection_account as connection_account_gitlab,
)
from ..google.implementation import run as google_run
from ..google.tests.fake_api import fake_google_workspace_api
from ..google.tests.functional_tests import (
    connection_account as connection_account_google,
)
from ..google.tests.functional_tests import google_workspace_connection_account
from ..jamf.implementation import run as jamf_run
from ..jamf.tests.functional_tests import connection_account as connection_account_jamf
from ..jira.implementation import run as jira_run
from ..jira.tests.functional_tests import connection_account as connection_account_jira
from ..linear.implementation import run as linear_run
from ..linear.tests.functional_tests import (
    connection_account as connection_account_linear,
)
from ..microsoft.implementation import run as microsoft_run
from ..microsoft.tests.functional_tests import (
    connection_account as connection_account_microsoft,
)
from ..models import SUCCESS, SYNC, ConnectionAccount
from ..rippling.implementation import run as rippling_run
from ..rippling.tests.functional_tests import (
    connection_account as connection_account_rippling,
)
from ..shortcut.implementation import run as shortcut_run
from ..shortcut.tests.functional_tests import (
    connection_account as connection_account_shortcut,
)
from ..store import Mapper, update_laika_objects
from ..tasks import update_integrations
from . import create_connection_account

bitbucket_con = connection_account_bitbucket
github_con = connection_account_github
gitlab_con = connection_account_gitlab
asana_con = connection_account_asana
jira_con = connection_account_jira
shortcut_con = connection_account_shortcut
google_con = connection_account_google
microsoft_con = connection_account_microsoft
rippling_con = connection_account_rippling
jamf_con = connection_account_jamf
linear_con = connection_account_linear


TEST_USER_MAPPER = Mapper(
    map_function=lambda x, y: x, keys=['Id'], laika_object_spec=USER
)


TEST_DATA_CODE = [
    ("connection_account_github", github_run),
    ("connection_account_bitbucket", bitbucket_run),
    ("connection_account_gitlab", gitlab_run),
]

TEST_DATA_DEVICE = [
    ("connection_account_jamf", jamf_run),
    # putting Rippling devices on hold because it is deprecated
    # ("connection_account_rippling", rippling_run)
]

TEST_DATA_USER = TEST_DATA_CODE + [
    ("connection_account_asana", asana_run),
    ("connection_account_shortcut", shortcut_run),
    ("connection_account_google", google_run),
    ("connection_account_rippling", rippling_run),
    ("connection_account_microsoft", microsoft_run),
    ("connection_account_linear", linear_run),
]

TEST_DATA_CHANGE_REQUEST = [
    ("connection_account_asana", asana_run),
    ("connection_account_jira", jira_run),
    ("connection_account_shortcut", shortcut_run),
    ("connection_account_linear", linear_run),
]


TEST_DATA = list(
    set(TEST_DATA_USER + TEST_DATA_CHANGE_REQUEST + TEST_DATA_CODE + TEST_DATA_DEVICE)
)


@pytest.fixture
def success_connection():
    with fake_google_workspace_api():
        yield google_workspace_connection_account(status=SUCCESS)


@pytest.mark.functional
def test_update_integrations_in_daily_schedule(success_connection):
    yesterday = datetime.now() - timedelta(days=1)
    setup_frequency(success_connection.id, DAILY, last_try=yesterday)
    update_integrations()
    assert LaikaObject.objects.exists()


@pytest.mark.functional
def test_update_integrations_ignore_onboarding(success_connection):
    yesterday = datetime.now() - timedelta(days=1)
    org = success_connection.organization
    org.state = ONBOARDING
    org.save()
    setup_frequency(success_connection.id, DAILY, last_try=yesterday)
    update_integrations()
    assert not LaikaObject.objects.exists()


@pytest.mark.functional
def test_update_integrations_in_weekly_schedule(success_connection):
    last_week = datetime.now() - timedelta(days=7)
    setup_frequency(success_connection.id, DAILY, last_try=last_week)
    update_integrations()
    assert LaikaObject.objects.exists()


@pytest.mark.functional
def test_update_integrations_when_daily_schedule_was_not_met(success_connection):
    success_connection.configuration_state = {'frequency': DAILY}
    success_connection.save()
    update_integrations()
    assert not LaikaObject.objects.exists()


@pytest.mark.functional
def test_update_integrations_when_weekly_schedule_was_not_met(success_connection):
    success_connection.configuration_state = {'frequency': WEEKLY}
    success_connection.save()
    update_integrations()
    assert not LaikaObject.objects.exists()


@pytest.mark.functional
def test_update_laika_objects_replace_old_data():
    connection_account = create_connection_account('github')
    update_laika_objects(connection_account, TEST_USER_MAPPER, [{'Id': 1}, {'Id': 2}])
    update_laika_objects(connection_account, TEST_USER_MAPPER, [{'Id': 1}])
    deleted = LaikaObject.objects.exclude(deleted_at=None)
    not_deleted = LaikaObject.objects.filter(deleted_at=None)

    assert not_deleted.count() == 1
    assert deleted.count() == 1
    assert not_deleted.first().data['Id'] == 1
    assert deleted.first().data['Id'] == 2


@pytest.mark.functional
@pytest.mark.xfail(raises=ConnectionAccountSyncing)
def test_delete_laika_object_sync_status():
    connection_account = create_connection_account('github')
    connection_account.status = SYNC
    update_laika_objects(connection_account, TEST_USER_MAPPER, [{'Id': 1}])
    connection_account.delete()


@pytest.mark.functional
@pytest.mark.parametrize("connection_account, run", TEST_DATA_CODE)
def test_repository_create_laika_objects(connection_account, run, request):
    connection = request.getfixturevalue(connection_account)
    run(connection)
    assert LaikaObject.objects.filter(object_type__type_name=REPOSITORY.type).exists()


@pytest.mark.functional
@pytest.mark.parametrize("connection_account, run", TEST_DATA_CODE)
def test_pull_request_create_laika_objects(connection_account, run, request):
    connection = request.getfixturevalue(connection_account)
    run(connection)
    assert LaikaObject.objects.filter(object_type__type_name=REPOSITORY.type).exists()


@pytest.mark.functional
@pytest.mark.parametrize("connection_account, run", TEST_DATA_USER)
def test_user_create_laika_objects(
    connection_account, run, request, create_permission_groups
):
    connection = request.getfixturevalue(connection_account)
    run(connection)
    assert LaikaObject.objects.filter(object_type__type_name=USER.type).exists()


@pytest.mark.functional
@pytest.mark.parametrize("connection_account, run", TEST_DATA)
def test_account_create_laika_objects(
    connection_account, run, request, create_permission_groups
):
    connection = request.getfixturevalue(connection_account)
    run(connection)
    assert LaikaObject.objects.filter(object_type__type_name=ACCOUNT.type).exists()


@pytest.mark.functional
@pytest.mark.parametrize("connection_account, run", TEST_DATA_CHANGE_REQUEST)
def test_change_request_create_laika_objects(connection_account, run, request):
    connection = request.getfixturevalue(connection_account)
    run(connection)
    assert LaikaObject.objects.filter(
        object_type__type_name=CHANGE_REQUEST.type
    ).exists()


@pytest.mark.functional
def test_update_laika_objects_contains_map_payload():
    connection_account = create_connection_account('github')
    mapper = Mapper(
        map_function=lambda x, y: {'Id': x['Id']}, keys=['Id'], laika_object_spec=USER
    )

    with pytest.raises(ValueError) as error:
        update_laika_objects(connection_account, mapper, [{'TypoId': 1}])

    assert str(error.value) == 'Mapping error raw: {\'TypoId\': 1}'


def setup_frequency(ca_id, frequency, last_try):
    ConnectionAccount.objects.filter(id=ca_id).update(
        updated_at=last_try, configuration_state={'frequency': frequency}
    )

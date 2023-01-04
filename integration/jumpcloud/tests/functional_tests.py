from pathlib import Path

import pytest
from httmock import HTTMock, urlmatch

from integration.encryption_utils import encrypt_value
from integration.exceptions import ConnectionAlreadyExists
from integration.jumpcloud.implementation import connect, raise_if_duplicate, run
from integration.models import ConnectionAccount
from integration.tests import create_connection_account
from objects.models import LaikaObject
from objects.system_types import ACCOUNT, USER, resolve_laika_object_type

FAKE_API_KEY = 'fake_api_key'
FAKE_ORGANIZATION = 'fake_organization'
PREFETCHED_ORGANIZATIONS = [{'id': 'fake_organization', 'value': {'name': 'Laika'}}]


def load_response(file_name):
    parent_path = Path(__file__).parent
    with open(parent_path / file_name, 'r') as file:
        return file.read()


def _organizations_response():
    return load_response('organizations_response.json')


def _users_response():
    return load_response('users_response.json')


def _system_users_response():
    return load_response('system_users_response.json')


@urlmatch(netloc='console.jumpcloud.com')
def _fake_jumpcloud_api(url, request):
    if 'organizations' in url.path:
        return _organizations_response()
    if 'systemusers' in url.path:
        return _system_users_response()
    if 'users' in url.path:
        return _users_response()
    raise ValueError('Unexpected operation for JumpCloud fake api')


def fake_jumpcloud_api():
    return HTTMock(_fake_jumpcloud_api)


def jumpcloud_connection_account(fetch_all: bool = False):
    return create_connection_account(
        'Jumpcloud',
        authentication={'prefetch_organization': PREFETCHED_ORGANIZATIONS},
        configuration_state={
            'credentials': {'apiKey': encrypt_value(FAKE_API_KEY)},
            'settings': {
                'selectedOrganizations': ['all'] if fetch_all else [FAKE_ORGANIZATION]
            },
        },
    )


@pytest.fixture
def connection_account():
    with fake_jumpcloud_api():
        yield jumpcloud_connection_account()


@pytest.fixture
def connection_account_with_all_organizations():
    with fake_jumpcloud_api():
        yield jumpcloud_connection_account(fetch_all=True)


@pytest.mark.functional
def test_jumpcloud_connect(connection_account):
    connection_account.authentication = {}
    connection_account.save()
    connect(connection_account)
    connection_account.refresh_from_db()
    got = connection_account.authentication['prefetch_organization']
    assert got == PREFETCHED_ORGANIZATIONS


@pytest.mark.functional
def test_jumpcloud_run(connection_account):
    lo_type_user = resolve_laika_object_type(connection_account.organization, USER)
    lo_type_account = resolve_laika_object_type(
        connection_account.organization, ACCOUNT
    )
    run(connection_account)
    assert LaikaObject.objects.filter(object_type=lo_type_account).count() == 1
    assert LaikaObject.objects.filter(object_type=lo_type_user).count() == 4


@pytest.mark.functional
def test_jumpcloud_run_all(connection_account_with_all_organizations):
    lo_type_user = resolve_laika_object_type(
        connection_account_with_all_organizations.organization, USER
    )
    run(connection_account_with_all_organizations)
    assert LaikaObject.objects.filter(object_type=lo_type_user).count() == 4


@pytest.mark.parametrize(
    'configuration_state',
    [
        {'credentials': {'apiKey': encrypt_value(FAKE_API_KEY)}},
        {
            'credentials': {'apiKey': encrypt_value(FAKE_API_KEY)},
            'settings': {'selectedOrganizations': [FAKE_ORGANIZATION]},
        },
    ],
)
@pytest.mark.functional
def test_jumpcloud_raise_already_exists(connection_account, configuration_state):
    connection_account.status = 'success'
    connection_account.save()

    duplicated_connection = ConnectionAccount.objects.create(
        alias='Duplicate Jumpcloud',
        authentication={},
        configuration_state=configuration_state,
        integration=connection_account.integration,
        organization=connection_account.organization,
    )
    with pytest.raises(ConnectionAlreadyExists):
        raise_if_duplicate(duplicated_connection)

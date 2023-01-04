from pathlib import Path

import pytest
from httmock import HTTMock, response, urlmatch

from integration.digitalocean.implementation import connect, raise_if_duplicate, run
from integration.encryption_utils import encrypt_value
from integration.error_codes import USER_INPUT_ERROR
from integration.exceptions import ConnectionAlreadyExists, ConnectionResult
from integration.models import ConnectionAccount, ErrorCatalogue
from integration.tests import create_connection_account
from objects.models import LaikaObject
from objects.system_types import ACCOUNT, MONITOR, resolve_laika_object_type

FAKE_ACCESS_TOKEN = 'FAKE_ACCESS_TOKEN'


def load_response(file_name):
    parent_path = Path(__file__).parent
    with open(parent_path / file_name, 'r') as file:
        return file.read()


def _monitors_response():
    return load_response('monitors_response.json')


@urlmatch(netloc='api.digitalocean.com')
def _fake_digitalocean_api(url, request):
    if 'monitoring/alerts' in url.path:
        return _monitors_response()
    raise ValueError('Unexpected operation for DigitalOcean fake api')


@urlmatch(netloc='api.digitalocean.com')
def _fake_digitalocean_api_fail(url, request):
    return response(400)


def fake_digitalocean_api():
    return HTTMock(_fake_digitalocean_api)


def digitalocean_connection_account():
    return create_connection_account(
        'DigitalOcean',
        configuration_state={
            'credentials': {'accessToken': encrypt_value(FAKE_ACCESS_TOKEN)},
        },
    )


@pytest.fixture
def connection_account():
    with fake_digitalocean_api():
        yield digitalocean_connection_account()


@pytest.mark.functional
def test_digitalocean_connect_failed():
    with pytest.raises(ConnectionResult), HTTMock(_fake_digitalocean_api_fail):
        ErrorCatalogue.objects.create(code=USER_INPUT_ERROR)
        connection_account = digitalocean_connection_account()
        connection_account.authentication = {}
        connection_account.save()
        connect(connection_account)


@pytest.mark.functional
def test_digitalocean_run(connection_account):
    lo_type_monitor = resolve_laika_object_type(
        connection_account.organization, MONITOR
    )
    lo_type_account = resolve_laika_object_type(
        connection_account.organization, ACCOUNT
    )
    run(connection_account)
    assert LaikaObject.objects.filter(object_type=lo_type_account).count() == 1
    assert LaikaObject.objects.filter(object_type=lo_type_monitor).count() == 3


@pytest.mark.functional
def test_digitalocean_raise_already_exists(connection_account):
    connection_account.status = 'success'
    connection_account.save()

    duplicated_connection = ConnectionAccount.objects.create(
        alias='Duplicate DigitalOcean',
        authentication={},
        configuration_state={
            'credentials': {'accessToken': encrypt_value(FAKE_ACCESS_TOKEN)}
        },
        integration=connection_account.integration,
        organization=connection_account.organization,
    )
    with pytest.raises(ConnectionAlreadyExists):
        raise_if_duplicate(duplicated_connection)

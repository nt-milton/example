import pytest as pytest

from integration.sentry import implementation
from integration.sentry.mapper import build_map_monitor_response_to_laika_object
from integration.sentry.tests.fake_api import fake_sentry_api
from integration.tests import create_connection_account
from objects.models import LaikaObject
from objects.system_types import MONITOR, resolve_laika_object_type

FAKE_API_AUTH_TOKEN = 'fake_api_auth_token'
USER = 'User'


@pytest.fixture
def connection_account():
    with fake_sentry_api():
        yield sentry_connection_account_last_run()


def sentry_connection_account_last_run(**kwargs):
    return create_connection_account(
        'Sentry',
        authentication={},
        configuration_state={
            'credentials': {'authToken': FAKE_API_AUTH_TOKEN},
            'settings': {
                'selectedOrganizations': ['heylaika'],
                'selectedProjects': [
                    "{\"slug\":\"project_1\",\"name\":\"project_1\","
                    "\"organization\":\"project_1\"}",
                    "{\"slug\":\"project_2\",\"name\":\"project_2\","
                    "\"organization\":\"project_2\"}",
                ],
            },
            'last_successful_run': 1643134127.128246,  # mock timestamp
        },
        **kwargs
    )


@pytest.mark.functional
def test_sentry_with_last_run(
    connection_account,
):
    organization = connection_account.organization
    mock_monitors = [
        dict(
            id='test1',
            title='monitor test',
            level='error',
            metadata=dict(title='meta'),
            status='unseen',
            firstSeen='2020-01-01T19:39:59.166407Z',
            project=dict(slug='project_1'),
        ),
        dict(
            id='test2',
            title='monitor test2',
            level='error',
            metadata=dict(title='meta'),
            status='unseen',
            firstSeen='2021-09-02T19:39:59.166407Z',
            project=dict(slug='project_1'),
        ),
    ]
    laika_object_type = resolve_laika_object_type(organization, MONITOR)
    for monitor in mock_monitors:
        LaikaObject.objects.create(
            object_type=laika_object_type,
            connection_account=connection_account,
            data=build_map_monitor_response_to_laika_object([], [])(
                monitor, 'test_connection'
            ),
        )

    implementation.run(connection_account)

    monitors = LaikaObject.objects.filter(
        connection_account=connection_account,
        object_type__display_name='Monitor',
        deleted_at=None,
    )

    assert connection_account.status == 'success'
    assert monitors.count() == 2

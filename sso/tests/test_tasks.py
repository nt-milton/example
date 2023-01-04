from unittest.mock import patch

from httmock import response

from sso.tasks import delete_inactive_okta_users

MOCKED_OKTA_RESPONSE = [
    {
        'id': '1',
    },
    {
        'id': '2',
    },
    {
        'id': '3',
    },
]

headers = {'Content-Type': 'application/json'}


@patch('requests.get', return_value=response(200, MOCKED_OKTA_RESPONSE, headers))
@patch('laika.okta.api.OktaApi.delete_user')
def test_delete_inactive_okta_users(delete_user_mock, get_okta_expired_users_mock):
    delete_inactive_okta_users('mocked_org_id')
    get_okta_expired_users_mock.assert_called_once()
    assert delete_user_mock.call_count == len(MOCKED_OKTA_RESPONSE)

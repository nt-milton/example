from unittest.mock import patch

from okta.models import User

from sso.okta.user_utils import delete_okta_user

MOCKED_USER_ID = '1234'


def mocked_get_user_by_email(email):
    return User({'id': MOCKED_USER_ID})


def mocked_delete_user(id):
    return True


@patch('sso.okta.user_utils.OktaApi.get_user_by_email', mocked_get_user_by_email)
@patch('sso.okta.user_utils.OktaApi.delete_user')
def test_delete_okta_user(mock_get_user_by_email):
    mocked_email = 'test@okta.com'
    delete_okta_user(mocked_email)
    mock_get_user_by_email.assert_called_once()
    # delete_user.assert_called_once()

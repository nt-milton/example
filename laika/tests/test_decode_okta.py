from unittest.mock import patch

import jwt
import pytest
from okta.models import Application
from okta.models import User as OktaUser
from okta_jwt_verifier.exceptions import JWTValidationException

from laika.constants import AUTH_GROUPS, OKTA
from laika.okta.auth import IDP, decode_okta, get_token_apps
from laika.tests.tests import OKTA_TOKEN, OKTA_TOKEN_EMAIL

TEST_EMAIL = 'test@heylaika.com'
JWT_MOCK = 'qwert12345babylon'


@patch('laika.okta.auth.decode', return_value={'email': TEST_EMAIL, 'sub': '1234asd'})
@patch(
    'laika.okta.auth.get_token_apps',
    return_value=(
        ['app1'],
        OktaUser(
            dict(
                id='fake_id',
                profile=dict(organizationId='12345abcdef', laika_role='LaikaViewer'),
                credentials=dict(provider=dict(name='OKTA')),
            )
        ),
    ),
)
def test_verify_okta_token(get_token_apps_mock, decode_mock):
    verified_token = decode_okta(JWT_MOCK, verify_exp=False)
    get_token_apps_mock.assert_called_once_with(
        verified_token, cache_name=f'apps_for_{TEST_EMAIL}', time_out=300
    )
    decode_mock.assert_called_once_with(JWT_MOCK, False, True, None)
    assert verified_token
    assert verified_token['email'] == TEST_EMAIL
    assert verified_token[IDP] == OKTA
    assert verified_token[AUTH_GROUPS] == ['app1']
    assert verified_token['role'] == 'LaikaViewer'


def test_verify_okta_token_exception():
    with patch(
        'laika.okta.auth.decode', side_effect=JWTValidationException('Invalid token')
    ):
        with pytest.raises(jwt.ExpiredSignatureError) as excinfo:
            decode_okta(JWT_MOCK)
        assert str(excinfo.value) == 'Signature has expired'


@patch(
    'laika.okta.api.OktaApi.get_user_by_email',
    return_value=OktaUser(
        dict(
            id='mocked_id',
            profile=dict(organizationId='12345abcdef', laika_role='LaikaViewer'),
            credentials=dict(provider=dict(name='OKTA')),
        )
    ),
)
@patch(
    'laika.okta.api.OktaApi.get_user_apps', return_value=[Application({'name': 'app1'})]
)
def test_get_token_apps(get_user_apps_mock, get_user_by_email_mock):
    verified_token = decode_okta(OKTA_TOKEN, verify_exp=False, verify=False)
    user_apps, okta_user = get_token_apps(
        verified_token,
        cache_name=f'apps_for_{OKTA_TOKEN_EMAIL}',
        time_out=300,  # 5minutes
    )
    get_user_by_email_mock.assert_called_once()
    get_user_apps_mock.assert_called_once()
    assert len(user_apps) == 1
    assert user_apps[0] == 'app1'
    assert okta_user.id == 'mocked_id'

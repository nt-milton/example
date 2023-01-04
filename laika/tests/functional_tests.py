from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError
from channels.testing import WebsocketCommunicator
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory

from feature.constants import mfa_feature_flag
from laika.asgi import application
from laika.auth import permission_required
from laika.tests.tests import COGNITO_TOKEN, bad_token
from laika.tests.utils import decode_without_verify_exp
from laika.utils.get_organization_by_user_type import get_organization_by_user_type
from organization.tests.factory import create_organization
from user.constants import ACTIVE, CONCIERGE, ROLE_ADMIN
from user.models import User
from user.tests.factory import create_user

GET_USER_PATCH = 'laika.middlewares.TokenAuthMiddleware.get_user'

TEST_PERMISSION = 'drive.add_driveevidence'
TEST_FLAG = 'MY_FLAG'
ADMIN_EMAIL = 'admin+laikaapp+heylaikadev@heylaika.com'


@pytest.fixture
def organization():
    return create_organization(flags=[], state=ACTIVE)


@pytest.fixture
def user(organization):
    return create_user(organization=organization, email=ADMIN_EMAIL, is_active=True)


@pytest.fixture
def user_inactive(organization):
    return create_user(organization=organization, email=ADMIN_EMAIL, is_active=False)


@pytest.mark.functional(feature_flags=[TEST_FLAG])
def test_flag_is_populated(graphql_client):
    organization, _ = graphql_client.context.values()
    assert organization.is_flag_active(TEST_FLAG)


@pytest.mark.functional(permissions=['drive.add_driveevidence'])
def test_permission_is_set(graphql_client):
    _, user = graphql_client.context.values()
    permission_codes = [p.codename for p in user.user_permissions.all()]
    assert 'add_driveevidence' in permission_codes


@pytest.mark.skip()
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@patch(GET_USER_PATCH)
async def test_successful_web_socket_connection(user_mkc, organization, user):
    with patch('jwt.decode') as decoded_mock:
        decoded_mock.return_value = {
            'custom:organizationId': organization.id,
            'email': user.email,
            'cognito:groups': ["OrganizationAdmin"],
        }

        user_mkc.return_value = user
        communicator = WebsocketCommunicator(
            application,
            f'/ws/alert/{organization.id}/{user.email}?token={COGNITO_TOKEN}',
        )
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
@patch('jwt.decode', wraps=decode_without_verify_exp)
async def test_web_socket_connection_bad_token(organization, user):
    with patch(GET_USER_PATCH) as user_mkc:
        user_mkc.return_value = user
        communicator = WebsocketCommunicator(
            application,
            '/ws/alert/31f3d57e-c1da-404c-b479-2d350c476fff'
            f'/{ADMIN_EMAIL}?token={bad_token}',
        )
        connected, _ = await communicator.connect()
        assert not connected


@pytest.mark.asyncio
@pytest.mark.django_db
@patch('jwt.decode', wraps=decode_without_verify_exp)
async def test_web_socket_connection_inactive_user(organization, user_inactive):
    with patch(GET_USER_PATCH) as user_mkc:
        user_mkc.return_value = user_inactive
        communicator = WebsocketCommunicator(
            application,
            '/ws/alert/31f3d57e-c1da-404c-b479-2d350c476fff'
            f'/{ADMIN_EMAIL}?token={COGNITO_TOKEN}',
        )
        connected, _ = await communicator.connect()
        assert not connected


@pytest.mark.functional
def test_get_organization_by_user_concierge(organization, user):
    organization_id = organization.id
    user.role = CONCIERGE

    organization_by_user = get_organization_by_user_type(user, organization_id)
    assert organization_by_user == organization


@pytest.mark.functional
def test_get_organization_by_user_laika(organization, user):
    organization_id = organization.id
    user.role = ROLE_ADMIN
    user.organization = organization

    organization_by_user = get_organization_by_user_type(user, organization_id)
    assert organization_by_user == user.organization


@pytest.mark.functional(feature_flags=[mfa_feature_flag], permissions=[TEST_PERMISSION])
def test_enforce_mfa_success(graphql_client, graphql_user):
    graphql_user.mfa = True
    request = RequestFactory().get('/')
    request.user = graphql_user

    method_with_permission(request)


@pytest.mark.functional(feature_flags=[mfa_feature_flag], permissions=[TEST_PERMISSION])
def test_enforce_mfa_with_error(graphql_client, graphql_user):
    request = RequestFactory().get('/')
    request.user = graphql_user

    with pytest.raises(PermissionDenied):
        method_with_permission(request)


@pytest.mark.functional
def test_setup_mfa_get_code(graphql_client, cognito):
    code = 'qr_code'
    cognito.associate_software_token = Mock(return_value={'SecretCode': code})

    response = graphql_client.execute(
        SETUP_MFA, variables={'accessToken': 'test_token'}
    )

    assert response['data']['setupMfa']['secret'] == code


@pytest.mark.functional
def test_verify_mfa(graphql_client, graphql_user, cognito):
    cognito.verify_software_token = Mock(return_value={'Status': 'SUCCESS'})
    response = graphql_client.execute(
        VERIFY_MFA, variables={'accessToken': 'test_token', 'code': '123456'}
    )
    assert User.objects.get(id=graphql_user.id).mfa
    assert response['data']['verifyMfa']['mfa']


@pytest.mark.functional
def test_verify_mfa_code_mismatch(graphql_client, graphql_user, cognito):
    error = {
        'Error': {
            'Code': 'EnableSoftwareTokenMFAException',
            'Message': 'Code mismatch and fail enable Software Token MFA',
        }
    }
    cognito.verify_software_token = Mock(
        side_effect=ClientError(error, 'VerifySoftwareToken')
    )

    response = graphql_client.execute(
        VERIFY_MFA, variables={'accessToken': 'test_token', 'code': ''}
    )

    assert not User.objects.get(id=graphql_user.id).mfa
    error, *_ = response['errors']
    assert error['message'] == 'Error validating MFA'


@pytest.mark.functional
def test_verify_mfa_status_no_success(graphql_client, graphql_user, cognito):
    cognito.verify_software_token = Mock(return_value={'Status': 'ERROR'})

    response = graphql_client.execute(
        VERIFY_MFA, variables={'accessToken': 'test_token', 'code': ''}
    )

    assert not User.objects.get(id=graphql_user.id).mfa
    error, *_ = response['errors']
    assert error['message'] == 'Error validating MFA'


@permission_required(TEST_PERMISSION)
def method_with_permission(info):
    # Dummy method to test mfa verification
    pass


@pytest.fixture()
def cognito():
    with patch('laika.aws.cognito.cognito') as module:
        yield module


SETUP_MFA = '''
        mutation setupMfa($accessToken: String!) {
            setupMfa(accessToken: $accessToken) {
              secret
            }
        }
    '''
VERIFY_MFA = '''
        mutation verifyMfa($accessToken: String!, $code: String!) {
            verifyMfa(accessToken: $accessToken, code: $code) {
              mfa
            }
        }
    '''

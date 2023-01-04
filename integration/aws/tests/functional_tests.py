import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import boto3
import pytest
from moto import mock_dynamodb, mock_iam, mock_organizations, mock_sts

from integration.account import set_connection_account_number_of_records
from integration.aws.aws_client import is_token_expired
from integration.aws.implementation import N_RECORDS, run
from integration.error_codes import USER_INPUT_ERROR
from integration.exceptions import ConfigurationError
from integration.settings import AWS_ROLE_NAME
from integration.tests import create_connection_account
from integration.tests.factory import create_error_catalogue, get_db_number_of_records
from laika.utils.exceptions import ServiceException
from objects.models import LaikaObject
from objects.system_types import ACCOUNT, USER, resolve_laika_object_type

FAKE_CLIENT_ARN = 'arn:aws:iam::209990397144:role/fake'
CONNECTION_ACCOUNT_ALIAS = 'AWS !"#$%&\'()*+,-./:;<=  >?@[\\]^_`   {|}~'


def _set_aws_resources():
    client = boto3.client('iam')
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
    client.create_role(
        RoleName=AWS_ROLE_NAME, AssumeRolePolicyDocument=json.dumps(policy)
    )
    external_iam_client = boto3.client(
        'iam',
        aws_access_key_id='access_key',
        aws_secret_access_key='secret_access_key',
        aws_session_token='session_token',
    )
    external_iam_client.create_user(UserName='test-external-user')
    external_organization_client = boto3.client(
        'organizations',
        aws_access_key_id='access_key',
        aws_secret_access_key='secret_access_key',
        aws_session_token='session_token',
    )
    external_organization_client.create_organization(FeatureSet='ALL')
    external_organization_client.create_account(
        Email='test@test.com', AccountName='test'
    )


@pytest.fixture
def connection_account():
    yield aws_connection_account()


@mock_iam
@mock_dynamodb
@mock_organizations
@mock_sts
@pytest.mark.functional
def tests_aws_integration_create_user_laika_objects(connection_account):
    lo_type = resolve_laika_object_type(connection_account.organization, USER)
    _set_aws_resources()
    run(connection_account)
    assert LaikaObject.objects.filter(object_type=lo_type).exists()


@mock_iam
@mock_dynamodb
@mock_organizations
@mock_sts
@pytest.mark.functional
def tests_aws_integration_create_user_laika_objects_without_service_account(
    connection_account,
):
    lo_type = resolve_laika_object_type(connection_account.organization, USER)
    _set_aws_resources()
    run(connection_account)
    assert LaikaObject.objects.filter(object_type=lo_type).exists()


@mock_iam
@mock_dynamodb
@mock_organizations
@mock_sts
@pytest.mark.functional
def test_aws_integration_create_account_laika_objects(connection_account):
    lo_type = resolve_laika_object_type(connection_account.organization, ACCOUNT)
    _set_aws_resources()
    run(connection_account)
    assert LaikaObject.objects.filter(object_type=lo_type).exists()


@mock_iam
@mock_dynamodb
@mock_organizations
@mock_sts
@pytest.mark.functional
def test_aws_integration_create_account_laika_objects_without_service_account(
    connection_account,
):
    lo_type = resolve_laika_object_type(connection_account.organization, ACCOUNT)
    _set_aws_resources()
    run(connection_account)
    assert LaikaObject.objects.filter(object_type=lo_type).exists()


@mock_iam
@mock_dynamodb
@mock_organizations
@mock_sts
@pytest.mark.functional
def test_aws_integrate_account_number_of_records(connection_account):
    run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


@mock_iam
@mock_dynamodb
@mock_organizations
@mock_sts
@pytest.mark.functional
def tests_aws_special_characters_integration_create_user_laika_objects(
    connection_account,
):
    connection_account.alias = CONNECTION_ACCOUNT_ALIAS
    lo_type = resolve_laika_object_type(connection_account.organization, USER)
    _set_aws_resources()
    run(connection_account)
    assert LaikaObject.objects.filter(object_type=lo_type).exists()


@mock_iam
@mock_dynamodb
@mock_organizations
@mock_sts
@pytest.mark.functional
def tests_aws_root_account_not_delete_normal_users(
    connection_account,
):
    connection_account.alias = CONNECTION_ACCOUNT_ALIAS
    lo_type = resolve_laika_object_type(connection_account.organization, USER)
    _set_aws_resources()

    with patch('integration.aws.implementation._retrieve_root_account') as mock:
        mock.return_value = ({'JoinedTimestamp': datetime.now()}, '209990397144')
        run(connection_account)
    assert (
        LaikaObject.objects.filter(deleted_at__isnull=True, object_type=lo_type).count()
        == 2
    )


@mock_iam
@mock_dynamodb
@mock_organizations
@mock_sts
@pytest.mark.functional
def test_aws_special_characters_integration_create_account_laika_objects(
    connection_account,
):
    connection_account.alias = CONNECTION_ACCOUNT_ALIAS
    lo_type = resolve_laika_object_type(connection_account.organization, ACCOUNT)
    _set_aws_resources()
    run(connection_account)
    assert LaikaObject.objects.filter(object_type=lo_type).exists()


@pytest.mark.functional
def test_is_token_expired_with_no_credentials(connection_account):
    assert is_token_expired(connection_account) is True


@pytest.mark.functional
def test_is_token_expired(connection_account):
    expired_timestamp = (
        (datetime.now(timezone.utc) - timedelta(hours=3))
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )
    connection_account.authentication = {
        'access_key_id': 'access_key_test',
        'secret_access_key': 'secret_key_test',
        'session_token': 'sessions_token_test',
        'token_expiration_time': expired_timestamp,
        'aws_regions': ['us-esast-1'],
    }
    assert is_token_expired(connection_account) is True


@pytest.mark.functional
def test_is_token_expired_returns_false(connection_account):
    non_expired_timestamp = (
        (datetime.now(timezone.utc) + timedelta(hours=3))
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )
    connection_account.authentication = {
        'access_key_id': 'access_key_test',
        'secret_access_key': 'secret_key_test',
        'session_token': 'sessions_token_test',
        'token_expiration_time': non_expired_timestamp,
        'aws_regions': ['us-esast-1'],
    }
    assert is_token_expired(connection_account) is False


@pytest.mark.functional
def test_aws_integrate_account_without_arn(connection_account):
    connection_account.configuration_state['credentials'] = {}
    with pytest.raises(ServiceException):
        run(connection_account)

    assert connection_account.status == 'error'


@mock_iam
@mock_organizations
@pytest.mark.functional
def test_aws_integrate_account_error_assuming_role(connection_account):
    create_error_catalogue(USER_INPUT_ERROR)
    with patch('integration.aws.aws_client.get_sts_client') as mock:
        mock.assume_role.side_effect = Exception('Error')
        with pytest.raises(ConfigurationError):
            run(connection_account)
        # 3 retries
        assert mock.call_count == 3

    assert connection_account.status == 'error'


@mock_iam
@mock_organizations
@pytest.mark.functional
def test_aws_integrate_account_response_without_credentials(connection_account):
    create_error_catalogue(USER_INPUT_ERROR)
    with patch('integration.aws.aws_client.get_sts_client') as mock:
        mock.assume_role.return_value = {}
        with pytest.raises(ConfigurationError):
            run(connection_account)
        # 3 retries
        assert mock.call_count == 3

    assert connection_account.status == 'error'


def aws_connection_account(**kwargs):
    return create_connection_account(
        'AWS',
        configuration_state=dict(credentials=dict(external_role_arn=FAKE_CLIENT_ARN)),
        **kwargs
    )

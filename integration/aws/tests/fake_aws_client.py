import os

import boto3
import pytest
from botocore.config import Config
from moto import mock_iam, mock_organizations, mock_sts

AWS_CONFIG = Config(retries={'max_attempts': 10, 'mode': 'standard'})


def _set_aws_credentials():
    os.environ['AWS_ACCESS_KEY_ID'] = 'fake_aws_access_key_id'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'fake_aws_secret_access_key'
    os.environ['AWS_SECURITY_TOKEN'] = 'fake_aws_security_token'
    os.environ['AWS_SESSION_TOKEN'] = 'fake_aws_session_token'


@pytest.fixture
def aws_credentials():
    _set_aws_credentials()


@pytest.fixture
def external_aws_credentials():
    _set_aws_credentials()


@pytest.fixture
def laika_iam_client(aws_credentials):
    with mock_iam():
        client = boto3.client('iam')
        yield client


@pytest.fixture
def laika_sts_client(aws_credentials):
    with mock_sts():
        client = boto3.client('sts', config=AWS_CONFIG)
        yield client


@pytest.fixture
def external_iam_client(external_aws_credentials):
    with mock_iam():
        client = boto3.client('iam', config=AWS_CONFIG)
        yield client


@pytest.fixture
def external_organization_client(external_aws_credentials):
    with mock_organizations():
        client = boto3.client('organizations', config=AWS_CONFIG)
        yield client

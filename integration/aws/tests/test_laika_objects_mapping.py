import json
from pathlib import Path

import pytest

from integration.aws.implementation import (
    AWS,
    AWSRootAccount,
    AWSUser,
    get_actions,
    map_root_account_to_laika_object,
    map_user_to_laika_object,
)

ORGANIZATION_NAME = 'Organization Name'


@pytest.fixture
def user_payload():
    parent_path = Path(__file__).parent
    get_user_path = parent_path / 'get_user.json'
    user = json.loads(open(get_user_path, 'r').read())
    get_organization_path = parent_path / 'get_organization.json'
    organization = json.loads(open(get_organization_path, 'r').read())
    get_groups_path = parent_path / 'get_groups.json'
    groups = json.loads(open(get_groups_path, 'r').read())
    is_admin = True
    mfa = True
    yield AWSUser(
        user=user,
        organization=organization,
        is_admin=is_admin,
        groups=', '.join(g['GroupName'] for g in groups['Groups']),
        mfa=mfa,
    )


@pytest.fixture
def root_account_payload():
    parent_path = Path(__file__).parent
    get_organization_path = parent_path / 'get_organization.json'
    organization = json.loads(open(get_organization_path, 'r').read())
    get_service_account_path = parent_path / 'get_service_account.json'
    root_account = json.loads(open(get_service_account_path, 'r').read())
    get_account_details_path = parent_path / 'get_account_details.json'
    roles = json.loads(open(get_account_details_path, 'r').read())
    yield AWSRootAccount(
        root_account=root_account, roles=roles, organization=organization
    )


@pytest.fixture
def incomplete_root_account_payload():
    parent_path = Path(__file__).parent
    get_organization_path = parent_path / 'get_incomplete_organization.json'
    organization = json.loads(open(get_organization_path, 'r').read())
    get_service_account_path = parent_path / 'get_service_account.json'
    root_account = json.loads(open(get_service_account_path, 'r').read())
    get_account_details_path = parent_path / 'get_account_details.json'
    roles = json.loads(open(get_account_details_path, 'r').read())
    yield AWSRootAccount(
        root_account=root_account, roles=roles, organization=organization
    )


TESTING_ALIAS = 'testing_aws_account'
GET_POLICIES_JSON = 'get_policies.json'


def test_laika_object_mapping_user_from_aws(user_payload):
    aws_user = user_payload.user
    got = map_user_to_laika_object(user_payload, TESTING_ALIAS)
    expected = {
        'Id': aws_user['UserId'],
        'First Name': aws_user['UserName'],
        'Last Name': '',
        # Email is blank after agreement with LCL about
        # leaving AWS users without email as they do not have one
        'Email': '',
        'Is Admin': user_payload.is_admin,
        'Title': '',
        ORGANIZATION_NAME: ORGANIZATION_NAME,
        'Roles': '',
        'Mfa Enabled': user_payload.mfa,
        'Mfa Enforced': '',
        'Connection Name': TESTING_ALIAS,
        'Source System': AWS,
        'Groups': user_payload.groups,
    }
    assert got == expected


def test_laika_object_mapping_service_account_for_aws(root_account_payload):
    got = map_root_account_to_laika_object(root_account_payload, TESTING_ALIAS)
    expected = get_expected_object(root_account_payload, ORGANIZATION_NAME)
    assert got == expected


def test_laika_object_mapping_root_account_for_aws_with_error(
    incomplete_root_account_payload,
):
    got = map_root_account_to_laika_object(
        incomplete_root_account_payload, TESTING_ALIAS
    )
    expected = get_expected_object(incomplete_root_account_payload, '')
    assert got == expected


def get_expected_object(source_obj, org_name):
    return {
        'Id': source_obj.root_account['Id'],
        'First Name': source_obj.root_account['Name'],
        'Last Name': '',
        'Email': source_obj.root_account['Email'],
        'Is Admin': True,
        'Title': '',
        ORGANIZATION_NAME: org_name,
        'Roles': str(source_obj.roles),
        'Mfa Enabled': '',
        'Mfa Enforced': '',
        'Groups': '',
        'Connection Name': TESTING_ALIAS,
        'Source System': AWS,
    }


def test_get_actions_mapping():
    parent_path = Path(__file__).parent
    get_policies_path = parent_path / 'get_policies.json'
    policies = json.loads(open(get_policies_path, 'r').read())
    got = get_actions(policies, "laika-integration-test-1")
    expected = [
        'acm:test',
        'acm:DescribeCertificate',
        'organizations:List*',
        'organizations:Describe*',
        'acm:ListCertificates',
    ]

    assert sorted(got) == sorted(expected)


def test_get_actions_mapping_empty():
    parent_path = Path(__file__).parent
    get_policies_path = parent_path / GET_POLICIES_JSON
    policies = json.loads(open(get_policies_path, 'r').read())
    got = get_actions(policies, "laika-integration-test-3")
    assert got == []


def test_get_actions_mapping_all_statement_types():
    parent_path = Path(__file__).parent
    get_policies_path = parent_path / GET_POLICIES_JSON
    policies = json.loads(open(get_policies_path, 'r').read())
    got = get_actions(policies, "laika-integration-test-4")
    expected = [
        "organizations:Describe*1",
        "organizations:Describe*2",
        "organizations:Describe*3",
        "organizations:Describe*4",
    ]

    assert sorted(got) == sorted(expected)

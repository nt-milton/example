import contextlib
import os.path
import time
from copy import deepcopy
from unittest.mock import patch

import pytest
from django.db import DatabaseError

from integration.constants import AWS_VENDOR, AZURE_VENDOR, GCP_VENDOR
from integration.encryption_utils import encrypt_value
from integration.models import SUCCESS, ConnectionAccount, Integration
from integration.tests.factory import create_connection_account, create_integration
from monitor.steampipe import (
    add_profile_query,
    build_profile_name,
    build_raw_steampipe_query,
    create_profile_before_run,
    get_vendor_name_from_query,
    monitor_context,
    profile_file_path,
    refresh_required,
    run,
)
from monitor.tests.factory import create_monitor
from organization.models import ACTIVE
from organization.tests.factory import create_organization
from user.tests.factory import create_user
from vendor.models import Vendor

FAKE_UUID = '3ce55377-bbc3-498b-b573-ad2d28c5bffb'
EXPECTED_FAKE_UUID = '3ce55377_bbc3_498b_b573_ad2d28c5bffb'


def test_build_organization_profile_name():
    profile_name = build_profile_name(FAKE_UUID)
    assert f'profile_{EXPECTED_FAKE_UUID}' == profile_name


@pytest.mark.functional
@pytest.mark.parametrize(
    'query', ['select * from anything', 'select * from any_thing', 'select * from ']
)
def text_get_vendor_name_from_query_exception(query):
    with pytest.raises(DatabaseError):
        get_vendor_name_from_query(query)


@pytest.mark.functional
@pytest.mark.parametrize(
    'query, expected',
    [
        ('select * from aws_iam_groups', AWS_VENDOR),
        ('select * from gcp_iam_role', GCP_VENDOR),
        ('select * from azure_ad_group', AZURE_VENDOR),
    ],
)
def test_get_vendor_name_from_query(query, expected):
    got = get_vendor_name_from_query(query)
    assert got == expected


@pytest.mark.parametrize(
    'query, template',
    [
        (
            'SELECT id, name, column FROM aws_users WHERE id=1;',
            'SELECT id, name, column FROM {profile_name}.aws_users WHERE id=1;',
        ),
        (
            'SELECT id FROM aws_users WHERE id=1;',
            'SELECT id FROM {profile_name}.aws_users WHERE id=1;',
        ),
        (
            'SELECT column_name FROM aws_users, aws_users WHERE id=1;',
            'SELECT column_name '
            'FROM {profile_name}.aws_users, '
            '{profile_name}.aws_users WHERE id=1;',
        ),
        (
            'SELECT id, name, column FROM aws_users, aws_users WHERE id=1;',
            'SELECT id, name, column '
            'FROM {profile_name}.aws_users, '
            '{profile_name}.aws_users WHERE id=1;',
        ),
        (
            'SELECT id FROM aws_users INNER JOIN aws_users WHERE id=1;',
            'SELECT id FROM {profile_name}.aws_users '
            'INNER JOIN {profile_name}.aws_users WHERE id=1;',
        ),
        (
            'SELECT id, name FROM aws_users INNER JOIN aws_users WHERE id=1;',
            'SELECT id, name FROM {profile_name}.aws_users '
            'INNER JOIN {profile_name}.aws_users WHERE id=1;',
        ),
        (
            'SELECT name as username, iam_group ->> "GroupName" as group_name '
            'FROM aws_users '
            'CROSS JOIN jsonb_array_elements(groups) AS iam_group '
            'WHERE id=1;',
            'SELECT name as username, iam_group ->> "GroupName" as group_name '
            'FROM {profile_name}.aws_users '
            'CROSS JOIN jsonb_array_elements(groups) AS iam_group '
            'WHERE id=1;',
        ),
        (
            'SELECT p as principal '
            'FROM aws_s3_bucket '
            'jsonb_array_elements_text(s -> "Principal" -> "AWS") as p '
            'WHERE p="*";',
            'SELECT p as principal '
            'FROM {profile_name}.aws_s3_bucket '
            'jsonb_array_elements_text(s -> "Principal" -> "AWS") as p '
            'WHERE p="*";',
        ),
        (
            'SELECT u1.id, u1.name FROM aws_users u1 '
            'WHERE u1.id in (SELECT u2.id FROM aws_users u2);',
            'SELECT u1.id, u1.name FROM {profile_name}.aws_users u1 '
            'WHERE u1.id in (SELECT u2.id FROM {profile_name}.aws_users u2);',
        ),
    ],
)
def test_build_raw_steampipe_query(query, template):
    connection_account = ConnectionAccount(id=1)
    got = build_raw_steampipe_query(connection_account, query)
    profile_name = build_profile_name(connection_account.id)
    expected = template.format(profile_name=profile_name)
    assert got == expected


def create_aws_connection():
    organization = create_organization()
    created_by = create_user(organization, email='heylaika@heylaika.com')
    integration = create_integration(AWS_VENDOR)
    return create_connection_account(
        1,
        status=SUCCESS,
        created_by=created_by,
        integration=integration,
        organization=organization,
        configuration_state={'credentials': 'test'},
        authentication={
            'access_key_id': '',
            'secret_access_key': '',
            'session_token': '',
            'token_expiration_time': time.time() + 60,
        },
    )


@pytest.mark.functional
def test_steampipe_runner(temp_query_runner):
    base_cnn = create_aws_connection()
    connection_accounts = [base_cnn]
    for _ in range(10):
        cnn = deepcopy(base_cnn)
        cnn.id = None
        cnn.save()
        connection_accounts.append(cnn)

    monitor = create_monitor('testing monitor', 'select * from aws_iam_group;')
    output = run(base_cnn.organization, monitor.query)
    query = 'select * from profile_{}.aws_iam_group;'
    for index, connection_account in enumerate(connection_accounts, start=1):
        first_column = output.results[-index].columns[0]
        assert query.format(connection_account.id) == first_column


def test_refresh_required():
    two_hours_ago = time.time() - 2 * 3600
    with patch('monitor.steampipe.os') as mock:
        mock.path.getmtime.return_value = two_hours_ago
        refresh = refresh_required(__file__)
        assert refresh


@pytest.mark.functional
def test_profile_is_created(steampipe_folder):
    cnn = create_aws_connection()
    profile = profile_file_path(cnn.id)
    assert not os.path.exists(profile)

    create_profile_before_run(cnn)
    assert os.path.exists(profile)


def test_no_refresh_required():
    ten_minutes_ago = time.time() - 10 * 60
    with patch('monitor.steampipe.os') as mock:
        mock.path.getmtime.return_value = ten_minutes_ago
        refresh = refresh_required(__file__)
        assert not refresh


def test_azuread_replacement():
    query = 'select * from azuread_user'
    profile_name = 'profile_1'
    expected = 'select * from azuread_profile_1.azuread_user'
    assert add_profile_query(profile_name, query) == expected


def test_context():
    connection_account = ConnectionAccount(
        id=1, integration=Integration(vendor=Vendor())
    )
    instance = monitor_context(connection_account)
    assert isinstance(instance, contextlib.nullcontext)


@pytest.mark.functional
def test_csp_context(steampipe_folder):
    connection_account = ConnectionAccount(
        id=1,
        configuration_state={
            'credentials': {'apiKey': encrypt_value('123'), 'email': 'test'}
        },
        status=SUCCESS,
        organization=create_organization(state=ACTIVE),
        authentication={},
        integration=create_integration('Heroku'),
    )
    connection_account.save()
    profile = profile_file_path(connection_account.id)
    with monitor_context(connection_account):
        assert os.path.exists(profile)
    assert not os.path.exists(profile)

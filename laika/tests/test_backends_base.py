from unittest.mock import patch

import django.utils.timezone as timezone
import pytest
from django.contrib.auth.models import Group
from okta.models import User as OktaUser

from laika.backends.base import (
    create_internal_user_based_on_token,
    get_internal_user,
    parse_api_token,
)
from organization.models import Organization
from user.constants import ROLE_VIEWER
from user.tests.factory import create_user


def test_parse_api_token_should_be_valid():
    is_valid, api_token = parse_api_token('APIKey random.token')

    assert is_valid
    assert api_token == 'random.token'


@pytest.mark.functional
def test_get_internal_user_update_role_from_okta(graphql_organization):
    Group.objects.create(name='premium_member')
    decoded_token = {
        'email': 'mock@test.com',
        'idp': 'OKTA',
        'username': '123456',
        'role': 'LaikaContributor',
    }
    create_user(
        graphql_organization,
        email='mock@test.com',
        role=ROLE_VIEWER,
        first_name='mock',
        last_name='test',
        invitation_sent=timezone.now(),
    )
    updated_user = get_internal_user(decoded_token)
    assert updated_user.role == 'OrganizationMember'


@pytest.mark.functional
@patch(
    'laika.okta.api.OktaApi.get_user_by_email',
    return_value=OktaUser(
        dict(
            id='mocked_id',
            profile=dict(
                organizationId='0b5df1ee-548c-11ed-bdc3-0242ac120002',
                laika_role='LaikaContributor',
                firstName='first name',
                lastName='last name',
                email='email@mock.com',
            ),
            credentials=dict(provider=dict(name='OKTA')),
        )
    ),
)
def test_create_internal_user_based_on_token_role_map(get_user_by_email):
    Group.objects.create(name='premium_member')
    Organization.objects.create(
        name='test org', id='0b5df1ee-548c-11ed-bdc3-0242ac120002'
    )
    decoded_token = {
        'email': 'mock@test.com',
        'idp': 'OKTA',
        'username': '123456',
        'role': 'LaikaContributor',
    }
    internal_user = create_internal_user_based_on_token(decoded_token)
    get_user_by_email.assert_called_once()
    assert internal_user.role == 'OrganizationMember'

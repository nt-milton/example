from unittest.mock import patch

import pytest

from blueprint.constants import COMPLIANCE, HUMAN_RESOURCES, TECHNICAL
from blueprint.helpers import (
    find_suggested_owner_responses,
    get_suggested_users,
    get_user_or_none,
)
from blueprint.tests.mock_files.get_suggested_owners import get_suggested_owners


@patch('blueprint.prescribe.get_suggested_users')
@pytest.mark.django_db()
def test_get_suggested_users(
    get_suggested_users_mock, graphql_organization, onboarding_response
):
    get_suggested_users_mock.return_value = get_suggested_owners(graphql_organization)
    suggested_users = get_suggested_users(graphql_organization.id)

    assert len(suggested_users) == 3
    assert suggested_users[COMPLIANCE].email == 'test+compliance@heylaika.com'
    assert suggested_users[TECHNICAL].email == 'test+technical@heylaika.com'
    assert suggested_users[HUMAN_RESOURCES].email == 'test+hr@heylaika.com'


@pytest.mark.django_db()
def test_get_suggested_users_himself(
    graphql_organization, graphql_user, onboarding_response_himself_poc
):
    suggested_users = get_suggested_users(graphql_organization.id)

    assert len(suggested_users) == 3
    assert suggested_users[COMPLIANCE].email == graphql_user.email
    assert suggested_users[TECHNICAL].email == graphql_user.email
    assert suggested_users[HUMAN_RESOURCES].email == graphql_user.email


@patch('blueprint.prescribe.get_suggested_users')
@pytest.mark.django_db()
def test_get_user_or_none(get_suggested_users_mock, graphql_organization):
    get_suggested_users_mock.return_value = get_suggested_owners(graphql_organization)
    response = {
        'type': 'email',
        'email': 'test+compliance@heylaika.com',
        'field': {
            'id': 'SfrUlDQrgSvO',
            'ref': 'primary_contact_email_address',
            'type': 'email',
        },
    }
    user = get_user_or_none(response, graphql_organization.id)

    assert user.email == 'test+compliance@heylaika.com'


@patch('blueprint.prescribe.get_suggested_users')
@pytest.mark.django_db()
def test_get_user_or_none_negative(get_suggested_users_mock, graphql_organization):
    get_suggested_users_mock.return_value = get_suggested_owners(graphql_organization)
    response = {
        'type': 'email',
        'email': 'test+dummy@heylaika.com',
        'field': {
            'id': 'SfrUlDQrgSvO',
            'ref': 'primary_contact_email_address',
            'type': 'email',
        },
    }
    user = get_user_or_none(response, graphql_organization.id)

    assert user is None


@patch('blueprint.prescribe.get_suggested_users')
@pytest.mark.django_db()
def test_get_user_or_none_with_invalid_email(
    get_suggested_users_mock, graphql_organization
):
    get_suggested_users_mock.return_value = get_suggested_owners(graphql_organization)
    response = {
        'type': 'text',
        'text': 'none an email',
        'field': {'id': 'SfrUlDQrgSvO', 'ref': 'primary_contact_text', 'type': 'text'},
    }
    user = get_user_or_none(response, graphql_organization.id)

    assert user is None


@patch('blueprint.prescribe.get_suggested_users')
@pytest.mark.django_db()
def test_get_user_or_none_email_text(get_suggested_users_mock, graphql_organization):
    get_suggested_users_mock.return_value = get_suggested_owners(graphql_organization)
    response = {
        'type': 'text',
        'text': 'test+technical@heylaika.com',
        'field': {
            'id': 'SfrUlDQrgSvO',
            'ref': 'primary_technical_contact_email_address',
            'type': 'text',
        },
    }
    user = get_user_or_none(response, graphql_organization.id)

    assert user.email == 'test+technical@heylaika.com'


def test_find_suggested_owner_responses_positive(get_typeform_result_response):
    questionary_responses = get_typeform_result_response
    responses = find_suggested_owner_responses(questionary_responses)

    assert len(responses) == 3
    assert (
        responses['primary_contact_email_address']['email']
        == 'test+compliance@heylaika.com'
    )
    assert (
        responses['primary_technical_contact_email_address']['text']
        == 'test+technical@heylaika.com'
    )
    assert (
        responses['primary_hr_contact_email_address']['email'] == 'test+hr@heylaika.com'
    )


def test_find_suggested_owner_responses_negative():
    questionary_responses = {}
    responses = find_suggested_owner_responses(questionary_responses)
    assert responses == {}

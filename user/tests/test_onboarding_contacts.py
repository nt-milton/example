import json
from pathlib import Path
from unittest.mock import patch

import pytest

from laika.tests import mock_responses
from organization.models import OnboardingResponse
from organization.tests import create_organization
from pentest.tests.factory import load_response
from user.tasks import (
    process_invite_onboarding_users,
    send_invite_onboarding_contacts,
    send_onboarding_technical_form,
)
from user.tests import create_user


@pytest.fixture
def get_questionary_response():
    response = load_response('typeform_response.json', path=Path(__file__).parents[0])
    with mock_responses([response]):
        yield json.loads(response)


@pytest.fixture
def questionary_response_user_is_all_poc():
    response = load_response(
        'typeform_response_user_is_all_poc.json', path=Path(__file__).parents[0]
    )
    with mock_responses([response]):
        yield json.loads(response)


@pytest.fixture
def questionary_response(graphql_organization, get_questionary_response):
    OnboardingResponse.objects.create(
        organization=graphql_organization,
        questionary_response=get_questionary_response,
        response_id="102test",
        questionary_id="12test",
    )
    return (
        OnboardingResponse.objects.filter(organization__id=graphql_organization.id)
        .values_list('questionary_response', flat=True)
        .distinct()[0]
    )


@pytest.fixture
def contacts(graphql_organization):
    primary_contact = (
        create_user(
            organization=graphql_organization,
            email='test+compliance+contact@heylaika.com',
            first_name='Compliance',
            last_name='Contact',
        ),
    )
    hr_contact = (
        create_user(
            organization=graphql_organization,
            email='test+hr+contact@heylaika.com',
            first_name='HR',
            last_name='Contact',
        ),
    )
    technical_contact = (
        create_user(
            organization=graphql_organization,
            email='test+technical+contact@heylaika.com',
            first_name='Technical',
            last_name='Contact',
        ),
    )
    return primary_contact, hr_contact, technical_contact


@pytest.fixture
def contacts_list(contacts):
    return [
        {
            'email_address': contact[0].email,
            'first_name': contact[0].first_name,
            'last_name': contact[0].last_name,
            'role': contact[0].role,
        }
        for contact in contacts
    ]


@pytest.fixture()
def contacts_list_user_is_contact_himself(graphql_user):
    return [
        {
            'email_address': graphql_user.email,
            'first_name': graphql_user.first_name,
            'last_name': graphql_user.last_name,
            'role': 'Compliance',
        }
    ]


@pytest.fixture
def technical_contact(contacts):
    return {
        'email_address': contacts[2][0].email,
        'first_name': contacts[2][0].first_name,
        'last_name': contacts[2][0].last_name,
        'role': 'Technical',
    }


@pytest.fixture
def contact_from_other_org(graphql_organization):
    other_org = create_organization(name='Other Org', flags=[])
    return create_user(organization=other_org, email='johnloe@test.com')


@patch('user.tasks.send_onboarding_technical_form', return_value=None)
@patch('user.tasks.send_invite_onboarding_contacts', return_value=[])
@pytest.mark.django_db()
def test_process_invite_onboarding_users(
    mock_send_invite_onboarding_contacts,
    mock_send_onboarding_technical_form,
    contacts,
    questionary_response,
    graphql_organization,
    graphql_user,
):
    process_invite_onboarding_users(
        questionary_response, graphql_organization, graphql_user
    )
    assert mock_send_invite_onboarding_contacts.call_once()
    assert mock_send_onboarding_technical_form.called


@patch('user.tasks.send_onboarding_technical_form', return_value=None)
@patch('user.tasks.send_invite_onboarding_contacts', return_value=[])
@pytest.mark.django_db()
def test_process_invite_onboarding_users_negative(
    mock_send_invite_onboarding_contacts,
    mock_send_onboarding_technical_form,
    contacts,
    questionary_response_user_is_all_poc,
    graphql_organization,
    graphql_user,
):
    process_invite_onboarding_users(
        questionary_response_user_is_all_poc, graphql_organization, graphql_user
    )
    assert mock_send_invite_onboarding_contacts.called
    assert not mock_send_onboarding_technical_form.called


@patch('user.tasks.send_onboarding_technical_form_email', return_value=None)
@pytest.mark.django_db()
def test_send_onboarding_technical_form(
    mock_send_onboarding_technical_form_email,
    technical_contact,
    graphql_organization,
    graphql_user,
):
    send_onboarding_technical_form(
        technical_contact, graphql_organization, graphql_user
    )
    assert mock_send_onboarding_technical_form_email.call_once()


@patch('user.tasks.send_onboarding_technical_form_email', return_value=None)
@pytest.mark.django_db()
def test_send_onboarding_technical_form_negative(
    mock_send_onboarding_technical_form_email, graphql_organization, graphql_user
):
    send_onboarding_technical_form({}, graphql_organization, graphql_user)
    assert not mock_send_onboarding_technical_form_email.called


@pytest.mark.django_db()
def test_send_invite_onboarding_contacts(
    contacts_list, graphql_organization, graphql_user
):
    invited_contacts = send_invite_onboarding_contacts(
        contacts_list, graphql_organization, graphql_user
    )
    assert len(invited_contacts) == 3
    assert invited_contacts[0].email == 'test+compliance+contact@heylaika.com'
    assert invited_contacts[1].email == 'test+hr+contact@heylaika.com'
    assert invited_contacts[2].email == 'test+technical+contact@heylaika.com'


@pytest.mark.django_db()
def test_send_invite_onboarding_contacts_from_other_org(
    contacts_list, contact_from_other_org, graphql_organization, graphql_user
):
    contacts_list[2]['email_address'] = contact_from_other_org.email
    invited_contacts = send_invite_onboarding_contacts(
        contacts_list, graphql_organization, graphql_user
    )
    assert len(invited_contacts) == 2  # contact_from_other_org is not invited


@pytest.mark.django_db()
def test_send_invite_onboarding_contacts_user_is_contact_himself(
    contacts_list_user_is_contact_himself, graphql_organization, graphql_user
):
    invited_contacts = send_invite_onboarding_contacts(
        contacts_list_user_is_contact_himself, graphql_organization, graphql_user
    )
    assert len(invited_contacts) == 0  # user is not invited

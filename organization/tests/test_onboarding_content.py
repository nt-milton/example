import json
from pathlib import Path

import pytest

from laika.tests import mock_responses
from organization.onboarding.onboarding_content import (
    get_onboarding_contact,
    get_onboarding_contacts,
    get_onboarding_vendor_names,
    get_technical_poc_answer,
)
from pentest.tests.factory import load_response


@pytest.fixture
def questionary_response():
    response = load_response('typeform_response.json', path=Path(__file__).parents[0])
    with mock_responses([response]):
        yield json.loads(response)


@pytest.fixture
def questionary_response_with_himself_questions():
    response = load_response(
        'typeform_response_with_himself_questions.json', path=Path(__file__).parents[0]
    )
    with mock_responses([response]):
        yield json.loads(response)


@pytest.mark.django_db
def test_get_onboarding_contacts_negative(graphql_user):
    contacts = get_onboarding_contacts({}, graphql_user)
    assert len(contacts) == 0


@pytest.mark.django_db
def test_get_onboarding_contacts_auto_assign_role(graphql_user, questionary_response):
    contacts = get_onboarding_contacts(questionary_response, graphql_user)
    assert len(contacts) == 3
    assert contacts[0]['role'] == 'Compliance'
    assert contacts[1]['role'] == 'Human Resources'
    assert contacts[2]['role'] == 'Technical'


@pytest.mark.django_db
def test_get_onboarding_contacts_with_himself_questions(
    graphql_user, questionary_response_with_himself_questions
):
    contacts = get_onboarding_contacts(
        questionary_response_with_himself_questions, graphql_user
    )
    assert len(contacts) == 3
    assert contacts[0]['email_address'] == graphql_user.email
    assert contacts[0]['first_name'] == graphql_user.first_name
    assert contacts[0]['last_name'] == graphql_user.last_name
    assert contacts[0]['role'] == 'Compliance'
    assert contacts[1]['email_address'] == 'test+hr+contact@heylaika.com'
    assert contacts[1]['role'] == 'Human Resources'
    assert contacts[2]['email_address'] == 'test+technical+contact@heylaika.com'
    assert contacts[2]['role'] == 'Technical'


def test_get_onboarding_vendor_names_multiple():
    vendor_questions = ['test_vendor_question']
    answer = {
        "field": {"ref": 'test_vendor_question'},
        "type": "choices",
        "choices": {"labels": ['The Vendor 1', 'The Vendor 2']},
    }
    mapper = {
        'The Vendor 1': 'vendor 1',
        'The Vendor 2': 'vendor 2',
    }
    result = get_onboarding_vendor_names(answer, vendor_questions, mapper)
    assert result is not None
    assert result == ['vendor 1', 'vendor 2']


def test_get_onboarding_vendor_names_single():
    vendor_questions = ['test_vendor_question']
    answer = {
        "field": {"ref": 'test_vendor_question'},
        "type": "choice",
        "choice": {"label": 'The Vendor 1'},
    }
    mapper = {
        'The Vendor 1': 'vendor 1',
    }
    result = get_onboarding_vendor_names(answer, vendor_questions, mapper)
    assert result is not None
    assert result == ['vendor 1']


def test_get_onboarding_vendor_names_boolean():
    vendor_questions = ['test_vendor_question']
    answer = {
        "field": {"ref": 'test_vendor_question'},
        "type": "boolean",
        "boolean": True,
    }
    result = get_onboarding_vendor_names(answer, vendor_questions, [])
    assert result is not None
    assert result == ['Slack']


def test_get_onboarding_contact_email():
    contact_questions = ['test_contact_question_email_address']
    answer = {
        "field": {"ref": 'test_contact_question_email_address'},
        "email": "test@test.com",
    }
    result = get_onboarding_contact(answer, contact_questions, {})
    assert result is not None
    assert result['email_address'] == 'test@test.com'


def test_get_onboarding_contact_text():
    contact_questions = ['test_contact_question_first_name']
    answer = {"field": {"ref": 'test_contact_question_first_name'}, "text": "test"}
    result = get_onboarding_contact(answer, contact_questions, {})
    assert result is not None
    assert result['first_name'] == 'test'


def test_get_technical_poc_answer():
    answer_mock = {
        'type': 'boolean',
        'field': {
            'ref': 'is_technical_poc',
        },
        'boolean': False,
    }
    is_technical_poc = get_technical_poc_answer(answer_mock)
    assert is_technical_poc is False

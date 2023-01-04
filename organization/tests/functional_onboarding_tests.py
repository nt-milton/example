import uuid
from unittest.mock import patch

import pytest

from organization.constants import QUESTIONNAIRE
from organization.models import OnboardingResponse
from organization.onboarding.onboarding_content import get_onboarding_form_text_answer
from organization.tests.mutations import (
    BOOK_ONBOARDING_MEETING,
    VALIDATE_ONBOARDING_MEETING,
)

from .queries import GET_ONBOARDING, GET_ONBOARDING_EXPERT

DATE_TIME_STRING = '2022-08-15T22:00:00-06:00'


@pytest.fixture
def onboarding_response(graphql_organization):
    return OnboardingResponse.objects.create(
        organization=graphql_organization,
        questionary_response='[]',
        response_id=1,
        questionary_id=1,
    )


@pytest.mark.functional(permissions=['organization.view_onboarding'])
@patch('organization.schema.validate_event', return_value=True)
@patch('organization.types.get_event', return_value={'start_time': DATE_TIME_STRING})
def test_get_onboarding(
    validate_event_mock, get_event_mock, graphql_client, graphql_organization
):
    calendly_event_test_id = str(uuid.uuid4())
    calendly_url_test = 'calendly_url'

    graphql_organization.onboarding.update(calendly_event_id_v2=calendly_event_test_id)
    graphql_organization.calendly_url = calendly_url_test
    graphql_organization.save()

    executed = graphql_client.execute(GET_ONBOARDING)
    response = executed['data']['onboarding']
    assert response['stateV2'] == QUESTIONNAIRE
    assert response['calendlyEventIdV2'] == calendly_event_test_id
    assert response['calendlyUrlV2'] == calendly_url_test
    assert response['architectMeetingV2'] == DATE_TIME_STRING


@pytest.mark.functional(permissions=['organization.change_onboarding'])
@patch(
    'organization.onboarding.onboarding_content.get_onboarding_form_answer',
    return_value=('', ''),
)
def test_get_onboarding_expert(
    get_onboarding_form_answer_mock,
    graphql_client,
    graphql_organization,
    onboarding_response,
):
    executed = graphql_client.execute(GET_ONBOARDING_EXPERT)
    response = executed['data']['getOnboardingExpert']

    assert response['firstName'] == ''
    assert response['lastName'] == ''
    assert response['email'] == ''


@pytest.mark.functional(permissions=['organization.change_onboarding'])
@patch(
    'organization.onboarding.onboarding_content.get_onboarding_form_answer',
    return_value=None,
)
def test_get_empty_onboarding_expert(
    get_onboarding_form_answer_mock, graphql_client, graphql_organization
):
    executed = graphql_client.execute(GET_ONBOARDING_EXPERT)
    response = executed['data']['getOnboardingExpert']

    assert response['firstName'] is None
    assert response['lastName'] is None
    assert response['email'] is None


@pytest.mark.functional(permissions=['organization.change_onboarding'])
@patch(
    'organization.onboarding.onboarding_content.get_onboarding_form_answer',
    return_value=('TEST', ''),
)
def test_get_onboarding_form_text_answer(
    get_onboarding_form_answer_mock, graphql_organization
):
    answer = get_onboarding_form_text_answer(graphql_organization, 'TEST_TEXT')

    assert answer == 'TEST'


@pytest.mark.functional(permissions=['organization.change_onboarding'])
def test_book_onboarding_meting(graphql_client, graphql_organization):
    calendly_event_id = str(uuid.uuid4())
    calendly_invitee_id = str(uuid.uuid4())

    executed = graphql_client.execute(
        BOOK_ONBOARDING_MEETING,
        variables={'eventId': calendly_event_id, 'inviteeId': calendly_invitee_id},
    )

    response = executed['data']['bookOnboardingMeeting']['onboarding']
    assert response['calendlyEventIdV2'] == calendly_event_id
    assert response['calendlyInviteeIdV2'] == calendly_invitee_id


@pytest.mark.functional(permissions=['organization.change_onboarding'])
@patch('organization.mutations.validate_event', return_value=True)
def test_validate_onboarding_meting(
    validate_event_mock, graphql_client, graphql_organization
):
    calendly_event_test_id = str(uuid.uuid4())
    graphql_organization.onboarding.update(calendly_event_id_v2=calendly_event_test_id)

    executed = graphql_client.execute(VALIDATE_ONBOARDING_MEETING)

    onboarding = graphql_organization.onboarding.first()
    response = executed['data']['validateOnboardingMeeting']['onboarding']
    assert response['id'] == onboarding.id

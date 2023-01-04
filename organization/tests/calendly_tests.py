from unittest.mock import patch

import pytest

from organization.calendly.rest_client import update_meeting_data
from organization.constants import ARCHITECT_MEETING, QUESTIONNAIRE

from .factory import create_organization

calendly_invitee_mock = {'cancelled': 'cancelled meeting'}


@pytest.mark.django_db
@patch(
    'organization.calendly.rest_client.get_invitee', return_value=calendly_invitee_mock
)
def test_update_meeting_data_when_cancelled(get_invitee_mock):
    organization = create_organization('Test Org')
    onboarding = organization.onboarding.first()
    onboarding.state_v2 = QUESTIONNAIRE
    onboarding.save()

    update_meeting_data(onboarding)

    assert onboarding.calendly_event_id_v2 is None
    assert onboarding.calendly_invitee_id_v2 is None
    assert onboarding.state_v2 == ARCHITECT_MEETING

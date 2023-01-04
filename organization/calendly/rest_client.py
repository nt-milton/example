import re

import requests

from laika.settings import DJANGO_SETTINGS
from organization.constants import ARCHITECT_MEETING

from .exceptions import ResourceNotAvailable

CALENDLY_BASE_URL = 'https://api.calendly.com'
CALENDLY_TOKEN = DJANGO_SETTINGS.get('CALENDLY_TOKEN')

HEADERS = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {CALENDLY_TOKEN}',
}


def update_meeting_data(onboarding):
    invitee = get_invitee(
        onboarding.calendly_event_id_v2,
        onboarding.calendly_invitee_id_v2,
    )
    if not invitee.get('new_invitee'):
        onboarding.state_v2 = ARCHITECT_MEETING
        onboarding.calendly_event_id_v2 = None
        onboarding.calendly_invitee_id_v2 = None
        onboarding.save()
        return

    new_event_id, new_invitee_id, *_ = re.search(
        'events/(.*)/invitees/(.*)', invitee['new_invitee']
    ).groups()
    onboarding.calendly_event_id_v2 = new_event_id
    onboarding.calendly_invitee_id_v2 = new_invitee_id
    onboarding.save()


def validate_event(onboarding):
    event = get_event(onboarding.calendly_event_id_v2)
    if event.get('cancellation'):
        update_meeting_data(onboarding)


def get_invitee(event_id, invitee_id):
    invitee = (
        requests.get(
            f'{CALENDLY_BASE_URL}/scheduled_events/{event_id}/invitees/{invitee_id}',
            headers=HEADERS,
        )
        .json()
        .get('resource')
    )
    if not invitee:
        raise ResourceNotAvailable(
            f'There are no invitees with invitee_id: {invitee_id}'
        )

    return invitee


def get_event(event_id):
    event = (
        requests.get(
            f'{CALENDLY_BASE_URL}/scheduled_events/{event_id}',
            headers=HEADERS,
        )
        .json()
        .get('resource')
    )
    if not event:
        raise ResourceNotAvailable(f'There are no events with event_id: {event_id}')
    return event

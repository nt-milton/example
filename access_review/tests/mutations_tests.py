import io

import pytest
from django.core.files import File

from access_review.models import AccessReview, AccessReviewUserEvent
from access_review.tests.factory import (
    create_access_review,
    create_access_review_object,
    create_access_review_vendor,
)

UPDATE_ACCESS_REVIEW_OBJECTS = '''
    mutation($input: [UpdateAccessReviewObjectInput]!) {
      updateAccessReviewObjects(input: $input) {
        accessReviewObjects {
            id
            notes
            isConfirmed
        }
      }
    }
'''

UPDATE_ACCESS_REVIEW_VENDOR = '''
    mutation($input: UpdateAccessReviewVendorInput!){
      updateAccessReviewVendor (input: $input){
        accessReviewVendor {
          id
          status
        }
      }
    }
'''


@pytest.fixture
def access_object(graphql_organization):
    yield create_access_review_object(graphql_organization)


@pytest.mark.functional(permissions=['access_review.change_accessreview'])
def test_access_object_mutation(graphql_client, access_object):
    notes = 'Test'
    response = graphql_client.execute(
        UPDATE_ACCESS_REVIEW_OBJECTS,
        variables={
            'input': [{'id': access_object.id, 'confirmed': True, 'notes': notes}]
        },
    )['data']['updateAccessReviewObjects']

    updated_objects = response['accessReviewObjects']
    user_events_accounts_reviewed = AccessReviewUserEvent.objects.filter(
        event=AccessReviewUserEvent.EventType.REVIEWED_ACCOUNTS
    )
    user_events_accounts_notes = AccessReviewUserEvent.objects.filter(
        event=AccessReviewUserEvent.EventType.CREATE_OR_UPDATE_ACCOUNTS_NOTES
    )
    access_object.refresh_from_db()
    assert len(user_events_accounts_reviewed) == 1
    assert len(user_events_accounts_notes) == 1
    assert access_object.is_confirmed
    assert updated_objects[0]['notes'] == notes


@pytest.mark.functional(permissions=['access_review.change_accessreview'])
def test_access_object_mutation_clear_attachment(
    graphql_client,
    access_object,
):
    access_object.note_attachment = File(io.BytesIO(b'Test'), name='test')
    access_object.save()
    graphql_client.execute(
        UPDATE_ACCESS_REVIEW_OBJECTS,
        variables={
            'input': [
                {
                    'id': access_object.id,
                    'clearAttachment': True,
                }
            ]
        },
    )
    user_events_accounts = AccessReviewUserEvent.objects.filter(
        event=AccessReviewUserEvent.EventType.CLEAR_ACCOUNT_ATTACHMENT
    )
    access_object.refresh_from_db()
    assert len(user_events_accounts) == 1
    assert access_object.note_attachment._file is None


@pytest.mark.functional(permissions=['access_review.change_accessreview'])
def test_update_ignore_none_fields(graphql_client, access_object):
    notes = 'Dummy Test'
    access_object.is_confirmed = True
    access_object.notes = notes
    access_object.save()

    graphql_client.execute(
        UPDATE_ACCESS_REVIEW_OBJECTS,
        variables={
            'input': [
                {
                    'id': access_object.id,
                    'confirmed': False,
                }
            ]
        },
    )
    user_events_accounts = AccessReviewUserEvent.objects.filter(
        event=AccessReviewUserEvent.EventType.UNREVIEWED_ACCOUNTS
    )
    assert len(user_events_accounts) == 1
    access_object.refresh_from_db()
    assert access_object.notes == notes
    assert not access_object.is_confirmed


@pytest.mark.functional(permissions=['access_review.change_accessreviewvendor'])
def test_update_access_review_vendor_mutation(
    graphql_client, graphql_organization, access_review_file
):
    status = 'completed'
    access_review = create_access_review(
        graphql_organization, access_review_file, AccessReview.Status.DONE
    )
    access_review_vendor_id = create_access_review_vendor(
        access_review=access_review
    ).id
    response = graphql_client.execute(
        UPDATE_ACCESS_REVIEW_VENDOR,
        variables={'input': {'id': str(access_review_vendor_id), 'status': status}},
    )['data']['updateAccessReviewVendor']
    access_review_vendor = response['accessReviewVendor']
    user_events_vendor = AccessReviewUserEvent.objects.filter(
        access_review=access_review,
        event=AccessReviewUserEvent.EventType.COMPLETE_ACCESS_REVIEW_VENDOR,
    )
    assert len(user_events_vendor) == 1
    assert access_review_vendor['status'] == status

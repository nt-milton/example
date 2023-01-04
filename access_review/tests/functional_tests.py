import json
from datetime import date, datetime, timedelta
from unittest.mock import patch

import celery.states
import pytest
from dateutil.relativedelta import relativedelta
from django.db.models import Q
from django_celery_results.models import TaskResult

from access_review.constants import (
    ACCESS_REVIEW_REMINDER,
    AR_REVIEWERS_ACTION_ITEM_DESCRIPTION,
    AR_REVIEWERS_ACTION_ITEM_NAME,
    AR_REVIEWERS_ACTION_ITEM_TYPE,
)
from access_review.evidence import get_access_review_object_updates
from access_review.models import (
    AccessReview,
    AccessReviewObject,
    AccessReviewPreference,
    AccessReviewUserEvent,
    AccessReviewVendor,
    AccessReviewVendorPreference,
)
from access_review.mutations import COMPLETED_ACTION_ITEM, RECURRENT_ACTION_ITEM
from access_review.mutations import (
    create_access_review_vendor_preference as set_access_review_vendor_preference,
)
from access_review.schema import build_list_vendors_filter, validate_in_scope_vendors
from access_review.tasks import send_access_review_overdue_emails
from access_review.tests.factory import (
    create_access_review,
    create_access_review_object,
    create_access_review_vendor,
    create_access_review_vendor_preference,
)
from access_review.utils import (
    ACCESS_REVIEW_ACTION_ITEM_DESCRIPTION_KEY,
    ACCESS_REVIEW_CONTINUE_LABEL_KEY,
    ACCESS_REVIEW_START_LABEL_KEY,
    ACCESS_REVIEW_TYPE,
    CONTROL_REFERENCE_ID,
    check_if_vendor_is_used_by_ongoing_ac,
    get_access_review_tray_keys,
    get_laika_object_permissions,
    return_in_scope_vendor_ids,
    return_integrated_vendor_ids,
)
from action_item.models import ActionItem, ActionItemStatus
from control.models import Control
from control.tests import create_control
from control.tests.factory import create_action_item
from integration.constants import ERROR, SUCCESS
from integration.github.implementation import run as github_run
from integration.github.tests.fake_api import fake_github_api
from integration.github.tests.functional_tests import github_connection_account
from integration.tests import create_connection_account
from objects.tests.factory import create_lo_with_connection_account
from organization.tests.factory import create_organization
from user.tests import create_user
from vendor.models import OrganizationVendorStakeholder
from vendor.tests.factory import create_organization_vendor, create_vendor


@pytest.fixture
def action_item(graphql_organization):
    return ActionItem.objects.create(
        due_date=date.today(),
        metadata={
            'referenceId': RECURRENT_ACTION_ITEM,
            'organizationId': str(graphql_organization.id),
        },
    )


@pytest.fixture
def access_review_preference(graphql_organization):
    return AccessReviewPreference.objects.create(organization=graphql_organization)


@pytest.fixture
@pytest.mark.functional
def access_review(graphql_organization, access_review_file):
    return create_access_review(graphql_organization, access_review_file)


@pytest.fixture
def access_review_vendor(access_review):
    return create_access_review_vendor(access_review=access_review)


@pytest.fixture
def access_review_kwargs(
    access_review,
    access_review_vendor,
    access_review_file,
):
    return {
        'access_review': access_review,
        'access_review_vendor': access_review_vendor,
        'evidence': access_review_file,
    }


@pytest.fixture
def access_review_object_unchanged(graphql_organization, access_review_kwargs):
    return create_access_review_object(
        graphql_organization,
        review_status=AccessReviewObject.ReviewStatus.UNCHANGED,
        **access_review_kwargs,
    )


@pytest.fixture
def access_review_object_revoked(graphql_organization, access_review_kwargs):
    return create_access_review_object(
        graphql_organization,
        review_status=AccessReviewObject.ReviewStatus.REVOKED,
        **access_review_kwargs,
    )


@pytest.fixture
def access_review_object_modified(graphql_organization, access_review_kwargs):
    return create_access_review_object(
        graphql_organization,
        review_status=AccessReviewObject.ReviewStatus.MODIFIED,
        **access_review_kwargs,
    )


GET_ACCESS_REVIEW = '''
    query accessReview {
        accessReview {
            id
            name
            createdAt
            completedAt
            dueDate
            status
            notes
            finalReportUrl
            helpModalOpened
            control
            accessReviewVendors {
                id
                isEnabledForCurrentUser
                vendor {
                    id
                }
                accessReviewObjects {
                    id
                    evidence
                    laikaObject {
                        id
                    }
                }
            }
        }
    }
'''

GET_ACCESS_REVIEW_WITH_VENDOR_FILTER = '''
    query accessReview($vendor: Int) {
        accessReview {
            id
            name
            accessReviewVendors(vendor: $vendor) {
                id
                accessReviewObjects {
                    id
                    reviewStatus
                    isConfirmed
                }
            }
        }
    }
'''


@pytest.mark.functional(permissions=['access_review.view_accessreview'])
def test_get_access_review_order_by_status(
    graphql_client,
    graphql_organization,
    access_review_object_unchanged,
    access_review_object_revoked,
    access_review_object_modified,
):
    response = graphql_client.execute(GET_ACCESS_REVIEW)
    access_review_response = response['data']['accessReview']
    access_review_vendor_response = access_review_response['accessReviewVendors'][0]
    access_review_objects_response = access_review_vendor_response[
        'accessReviewObjects'
    ]
    assert access_review_objects_response[0]['id'] == str(
        access_review_object_modified.id
    )
    assert access_review_objects_response[1]['id'] == str(
        access_review_object_revoked.id
    )
    assert access_review_objects_response[2]['id'] == str(
        access_review_object_unchanged.id
    )


def get_url_without_params(url: str) -> str:
    return url[: url.find('?')]


@pytest.mark.functional(permissions=['access_review.view_accessreview'])
def test_get_access_review_in_progress(
    graphql_client, graphql_organization, graphql_user, access_review_file
):
    access_review = create_access_review(graphql_organization, access_review_file)

    vendor_with_user = create_vendor(name='vendor_with_user')
    access_review_vendor_with_user = create_access_review_vendor(
        access_review=access_review, vendor=vendor_with_user
    )
    access_review_vendor_preference_with_user = create_access_review_vendor_preference(
        graphql_organization, vendor_with_user
    )
    access_review_vendor_preference_with_user.reviewers.set([graphql_user])

    vendor_without_user = create_vendor(name='vendor_without_user')
    access_review_vendor_without_user = create_access_review_vendor(
        access_review=access_review, vendor=vendor_without_user
    )
    create_access_review_vendor_preference(graphql_organization, vendor_without_user)

    access_review_object = create_access_review_object(
        graphql_organization,
        access_review=access_review,
        access_review_vendor=access_review_vendor_with_user,
        evidence=access_review_file,
    )
    control = Control.objects.create(
        organization=graphql_organization,
        reference_id=CONTROL_REFERENCE_ID,
        name='Test Control',
    )
    response = graphql_client.execute(GET_ACCESS_REVIEW)
    access_review_response = response['data']['accessReview']
    access_review_vendors_response = access_review_response['accessReviewVendors']
    access_review_objects_response = access_review_vendors_response[0][
        'accessReviewObjects'
    ]
    vendor = access_review_vendors_response[0]['vendor']
    access_review_objects_response = access_review_vendors_response[0][
        'accessReviewObjects'
    ]
    assert access_review_response['id'] == str(access_review.id)
    assert access_review_response['name'] == access_review.name
    assert get_url_without_params(
        access_review_response['finalReportUrl']
    ) == get_url_without_params(access_review.final_report.url)
    assert len(access_review_vendors_response) == 2
    assert access_review_vendors_response[0]['id'] == str(
        access_review_vendor_with_user.id
    )
    assert access_review_vendors_response[0]['isEnabledForCurrentUser']
    assert access_review_vendors_response[1]['id'] == str(
        access_review_vendor_without_user.id
    )
    assert not access_review_vendors_response[1]['isEnabledForCurrentUser']
    assert vendor['id'] == str(access_review_vendor_with_user.vendor.id)
    assert len(access_review_objects_response) == 1
    assert access_review_objects_response[0]['evidence'] is not None
    assert access_review_objects_response[0]['laikaObject']['id'] == str(
        access_review_object.laika_object.id
    )
    assert str(control.id) == access_review_response['control']


@pytest.mark.functional(permissions=['access_review.view_accessreview'])
def test_get_access_review_with_vendor_filter(
    graphql_client, graphql_organization, access_review_file
):
    access_review = create_access_review(graphql_organization, access_review_file)
    AccessReviewVendor.objects.create(
        access_review=access_review, vendor=create_vendor(name='first')
    )
    access_review_vendor = AccessReviewVendor.objects.create(
        access_review=access_review, vendor=create_vendor(name='second')
    )
    create_access_review_object(
        graphql_organization, access_review, access_review_vendor
    )

    response = graphql_client.execute(
        GET_ACCESS_REVIEW_WITH_VENDOR_FILTER,
        variables={'vendor': access_review_vendor.vendor_id},
    )

    access_review_response = response['data']['accessReview']
    access_review_vendor_response = access_review_response['accessReviewVendors'][0]
    review_object = access_review_vendor_response['accessReviewObjects'][0]
    assert len(access_review_response['accessReviewVendors']) == 1
    assert access_review_vendor_response['id'] == str(access_review_vendor.id)
    assert review_object['reviewStatus'] == AccessReviewObject.ReviewStatus.UNCHANGED


@pytest.mark.functional(permissions=['access_review.view_accessreview'])
def test_get_access_review_done_status(
    graphql_client, graphql_organization, access_review_file
):
    create_access_review(
        graphql_organization, access_review_file, AccessReview.Status.DONE
    )
    response = graphql_client.execute(GET_ACCESS_REVIEW)
    access_review_response = response['data']['accessReview']
    assert not access_review_response


@pytest.fixture
def connection_account(graphql_organization):
    with fake_github_api():
        yield github_connection_account(organization=graphql_organization)


CREATE_ACCESS_REVIEW = '''
    mutation($input: AccessReviewInput!) {
      createAccessReview(input: $input) {
        accessReview {
            id
            name
            createdAt
            completedAt
            dueDate
            status
            notes
            finalReportUrl
            accessReviewVendors {
                id
                accessReviewObjects {
                    id
                }
            }
        }
      }
    }
    '''

UPDATE_ACCESS_REVIEW_STATUS = '''
mutation updateAccessReview($input: UpdateAccessReviewInput!){
  updateAccessReview (input: $input){
    accessReview {
      id
      name
      status
    }
  }
}'''


@pytest.mark.functional(permissions=['access_review.add_accessreview'])
def test_create_access_review(
    graphql_user,
    graphql_client,
    graphql_organization,
    connection_account,
    action_item,
    access_review_preference,
):
    github_run(connection_account)
    vendor = connection_account.integration.vendor
    access_review_vendor_preference = create_access_review_vendor_preference(
        graphql_organization, vendor
    )
    access_review_vendor_preference.reviewers.set([graphql_user])
    create_access_review_input = {
        'input': dict(
            name='Test',
            dueDate='2022-03-30',
            notes='notes',
        )
    }
    graphql_client.execute(CREATE_ACCESS_REVIEW, variables=create_access_review_input)
    access_review = AccessReview.objects.get(name='Test')
    access_review_vendors = AccessReviewVendor.objects.filter(
        access_review=access_review
    )
    access_review_objects = AccessReviewObject.objects.filter(
        access_review_vendor=access_review_vendors[0]
    )
    action_item.refresh_from_db()
    second_action_item = ActionItem.objects.get(
        metadata__type='access_review',
        metadata__organizationId=str(graphql_organization.id),
    )
    user_events_created = AccessReviewUserEvent.objects.filter(
        access_review=access_review,
        event=AccessReviewUserEvent.EventType.CREATE_ACCESS_REVIEW,
    )
    assert len(user_events_created) == 1
    assert access_review.status == AccessReview.Status.IN_PROGRESS
    assert len(access_review_objects) > 0
    assert len(access_review_vendors) > 0
    assert action_item.due_date == access_review_preference.due_date
    assert action_item.recurrent_schedule == access_review_preference.frequency
    assert list(action_item.assignees.all()) == [graphql_user]
    assert list(second_action_item.assignees.all()) == [graphql_user]


@pytest.mark.functional(permissions=['access_review.change_accessreview'])
def test_update_access_review_status(
    graphql_organization, graphql_client, access_review_file
):
    access_review = create_access_review(
        graphql_organization, access_review_file, AccessReview.Status.DONE
    )
    action_item = create_action_item(
        name=AR_REVIEWERS_ACTION_ITEM_NAME,
        description=AR_REVIEWERS_ACTION_ITEM_DESCRIPTION,
        due_date=access_review.due_date,
        is_required=True,
        metadata={
            'type': AR_REVIEWERS_ACTION_ITEM_TYPE,
            'accessReviewId': str(access_review.id),
            'organizationId': str(graphql_organization.id),
        },
        status='new',
    )
    graphql_client.execute(
        UPDATE_ACCESS_REVIEW_STATUS,
        variables={'input': {'id': access_review.id, 'status': 'canceled'}},
    )
    access_review_modified = AccessReview.objects.get(id=access_review.id)
    user_events_canceled = AccessReviewUserEvent.objects.filter(
        access_review=access_review,
        event=AccessReviewUserEvent.EventType.CANCEL_ACCESS_REVIEW,
    )
    action_item.refresh_from_db()
    assert action_item.status == ActionItemStatus.NOT_APPLICABLE
    assert len(user_events_canceled) == 1
    assert access_review_modified.status == 'canceled'


ADD_REVIEW = '''
    mutation ($input: OverrideReviewerInput!) {
      overrideReviewers(input: $input) {
        accessReviewVendorPreference {
            id
        }
      }
    }
'''


def users(organization):
    user1 = create_user(
        organization, email='user1@mail.com', username='test-user-1-username'
    )
    user2 = create_user(
        organization, email='user2@mail.com', username='test-user-2-username'
    )
    return user1, user2


@pytest.fixture
def new_vendors(graphql_organization, connection_account):
    user1, _ = users(graphql_organization)
    github_run(connection_account)
    vendor_1 = connection_account.integration.vendor
    create_access_review_vendor_preference(graphql_organization, vendor_1)
    vendor_2 = create_vendor()
    create_organization_vendor(graphql_organization, vendor_2),
    create_connection_account(
        vendor_name=vendor_1.name,
        organization=graphql_organization,
        created_by=user1,
        vendor=vendor_1,
    )
    create_connection_account(
        vendor_name=vendor_2.name,
        organization=graphql_organization,
        created_by=user1,
        vendor=vendor_2,
    )
    return vendor_1, vendor_2


@pytest.mark.functional(
    permissions=['access_review.change_accessreviewvendorpreference']
)
def test_add_reviewers(graphql_client, graphql_organization, connection_account):
    user1, user2 = users(graphql_organization)
    vendor = connection_account.integration.vendor
    ar_vendor_preference = create_access_review_vendor_preference(
        graphql_organization, vendor
    )
    graphql_client.execute(
        ADD_REVIEW,
        variables={
            'input': dict(
                vendorPreferenceId=vendor.id,
                reviewersIds=[user1.username, user2.username],
            )
        },
    )
    reviewers = ar_vendor_preference.reviewers.all()
    assert all(user in reviewers for user in [user1, user2])


@pytest.mark.functional(
    permissions=['access_review.change_accessreviewvendorpreference']
)
def test_override_reviewers(graphql_client, graphql_organization, connection_account):
    user1, user2 = users(graphql_organization)
    vendor = connection_account.integration.vendor
    ar_vendor_preference = create_access_review_vendor_preference(
        graphql_organization, vendor
    )
    ar_vendor_preference.reviewers.add(user1)
    graphql_client.execute(
        ADD_REVIEW,
        variables={
            'input': dict(vendorPreferenceId=vendor.id, reviewersIds=[user2.username])
        },
    )
    reviewers = ar_vendor_preference.reviewers.all()
    assert user2 in reviewers
    assert user1 not in reviewers


GET_ACCESS_REVIEW_PREFERENCES = '''
    query accessReviewPreferences($filter: JSONString) {
        accessReviewPreferences(filter: $filter) {
            inScopeVendors {
                id
                name
                isInScope
                isIntegrated
            }
            preferences {
                frequency
                criticality
            }
        }
    }
'''


@pytest.mark.functional(permissions=['access_review.view_accessreviewpreference'])
@patch('access_review.schema.Q')
def test_get_access_review_preference_vendors(
    mocked_q,
    graphql_client,
    graphql_organization,
    connection_account,
):
    # Mocking Q instance because UNACCENT function is not supported in sqlite
    connection_account.organization = graphql_organization
    connection_account.save()
    mocked_q.return_value = Q()
    github_run(connection_account)
    vendor = connection_account.integration.vendor
    create_access_review_vendor_preference(graphql_organization, vendor)
    response = graphql_client.execute(GET_ACCESS_REVIEW_PREFERENCES)
    access_review_preferences_response = response['data']['accessReviewPreferences']
    in_scope_vendor = access_review_preferences_response['inScopeVendors'][0]
    assert in_scope_vendor['id'] == str(vendor.id)
    assert in_scope_vendor['name'] == vendor.name
    assert in_scope_vendor['isInScope'] is True
    assert in_scope_vendor['isIntegrated'] is True
    assert access_review_preferences_response['preferences'] is None


@pytest.mark.functional(permissions=['access_review.view_accessreviewpreference'])
@patch('access_review.schema.Q')
def test_get_all_in_scope_vendors_filtered_should_be_empty(
    mocked_q, graphql_client, graphql_organization, connection_account
):
    # Mocking Q instance because UNACCENT function is not supported in sqlite
    mocked_q.return_value = Q(('id__in', []), ('name__unaccent__icontains', ''))
    github_run(connection_account)
    vendor = connection_account.integration.vendor
    create_access_review_vendor_preference(graphql_organization, vendor, False)
    response = graphql_client.execute(
        GET_ACCESS_REVIEW_PREFERENCES,
        variables={'filter': json.dumps({'inScope': True})},
    )
    access_review_preferences_response = response['data']['accessReviewPreferences']
    in_scope_vendor = access_review_preferences_response['inScopeVendors']
    assert len(in_scope_vendor) == 0


ADD_ACCESS_REVIEW_PREFERENCES = '''
    mutation ($input: AccessReviewVendorPreferenceInput!) {
      createAccessReviewPreference(input: $input) {
        accessReviewPreference {
            frequency
        }
      }
    }
'''

NUMBER_OF_USERS_PER_TEST = 3


@pytest.mark.functional(
    permissions=['access_review.change_accessreviewvendorpreference']
)
def test_auto_set_in_scope_false_access_review_preferences(
    graphql_client,
    graphql_organization,
    graphql_user,
    connection_account,
    action_item,
):
    new_vendor = create_vendor()
    organization_vendor = create_organization_vendor(graphql_organization, new_vendor)
    internal_stakeholders = [
        OrganizationVendorStakeholder.objects.create(
            sort_index=index,
            organization_vendor=organization_vendor,
            stakeholder=create_user(
                graphql_organization, email=f'user_{index}@heylaika.com'
            ),
        ).stakeholder
        for index in range(NUMBER_OF_USERS_PER_TEST)
    ]
    organization_vendor.internal_stakeholders.set(internal_stakeholders)
    create_connection_account(
        vendor_name=new_vendor.name,
        organization=graphql_organization,
        created_by=graphql_user,
        vendor=new_vendor,
    )
    vendor = connection_account.integration.vendor
    create_access_review_vendor_preference(
        organization=graphql_organization, vendor=vendor, in_scope=True
    )
    graphql_client.execute(
        ADD_ACCESS_REVIEW_PREFERENCES,
        variables={
            'input': dict(
                vendorIds=['2'],
                dueDate='2022-05-09T05:00:00.000Z',
                frequency='quaterly',
            )
        },
    )
    in_scope_vendor = AccessReviewVendorPreference.objects.filter(in_scope=True)
    out_of_scope_vendor = AccessReviewVendorPreference.objects.filter(in_scope=False)
    action_item.refresh_from_db()
    access_review_preference = AccessReviewPreference.objects.filter(
        organization=graphql_organization
    ).first()
    assert in_scope_vendor[0].vendor.id == new_vendor.id
    assert out_of_scope_vendor[0].vendor.id == vendor.id
    assert list(in_scope_vendor[0].reviewers.all()) == internal_stakeholders
    assert action_item.due_date == access_review_preference.due_date
    assert action_item.recurrent_schedule == access_review_preference.frequency
    assert list(action_item.assignees.all()) == [graphql_client.context.get('user')]


@pytest.fixture
def access_review_testing_vendor():
    return create_vendor('access_review_testing_vendor')


@pytest.fixture
def alternative_organization():
    return create_organization('alternative_organization')


@pytest.fixture
def alternative_organization_vendor(
    alternative_organization, access_review_testing_vendor
):
    return create_organization_vendor(
        alternative_organization, access_review_testing_vendor
    )


@pytest.fixture
def alternative_organization_stakeholder(
    alternative_organization, alternative_organization_vendor
):
    return OrganizationVendorStakeholder.objects.create(
        sort_index=0,
        organization_vendor=alternative_organization_vendor,
        stakeholder=create_user(alternative_organization, email='user@heylaika.com'),
    ).stakeholder


@pytest.mark.functional(
    permissions=['access_review.change_accessreviewvendorpreference']
)
def test_create_access_review_preferences_does_not_assign_users_from_another_org(
    graphql_client,
    graphql_organization,
    graphql_user,
    access_review_testing_vendor,
    alternative_organization_vendor,
    alternative_organization_stakeholder,
):
    alternative_organization_vendor.internal_stakeholders.set(
        [alternative_organization_stakeholder]
    )
    organization_vendor = create_organization_vendor(
        graphql_organization, access_review_testing_vendor
    )
    organization_stakeholder = OrganizationVendorStakeholder.objects.create(
        sort_index=0, organization_vendor=organization_vendor, stakeholder=graphql_user
    ).stakeholder
    organization_vendor.internal_stakeholders.set([organization_stakeholder])
    create_access_review_vendor_preference(
        organization_vendor=alternative_organization_vendor, in_scope=True
    )
    create_access_review_vendor_preference(
        organization_vendor=organization_vendor, in_scope=True
    )
    graphql_client.execute(
        ADD_ACCESS_REVIEW_PREFERENCES,
        variables={
            'input': dict(
                vendorIds=[access_review_testing_vendor.id],
                dueDate='2022-05-09T05:00:00.000Z',
                frequency='quaterly',
            )
        },
    )
    access_review_vendor_preference = AccessReviewVendorPreference.objects.get(
        organization_vendor__organization=graphql_organization,
        organization_vendor__vendor=access_review_testing_vendor,
    )
    assert list(access_review_vendor_preference.reviewers.all()) == [graphql_user]


@pytest.mark.functional(
    permissions=['access_review.change_accessreviewvendorpreference']
)
def test_create_access_review_preferences_does_not_take_preferences_from_another_org(
    graphql_client,
    graphql_organization,
    graphql_user,
    access_review_testing_vendor,
    alternative_organization,
    alternative_organization_vendor,
    alternative_organization_stakeholder,
):
    alternative_organization_vendor.internal_stakeholders.set(
        [alternative_organization_stakeholder]
    )
    set_access_review_vendor_preference(
        [access_review_testing_vendor.id], alternative_organization
    )
    alternative_access_review_vendor_preference = (
        AccessReviewVendorPreference.objects.filter(
            organization=alternative_organization,
            vendor=access_review_testing_vendor,
        ).first()
    )
    organization_vendor = create_organization_vendor(
        graphql_organization, access_review_testing_vendor
    )
    organization_stakeholder = OrganizationVendorStakeholder.objects.create(
        sort_index=0, organization_vendor=organization_vendor, stakeholder=graphql_user
    ).stakeholder
    organization_vendor.internal_stakeholders.set([organization_stakeholder])

    graphql_client.execute(
        ADD_ACCESS_REVIEW_PREFERENCES,
        variables={
            'input': dict(
                vendorIds=[access_review_testing_vendor.id],
                dueDate='2022-05-09T05:00:00.000Z',
                frequency='quaterly',
            )
        },
    )
    access_review_vendor_preference = AccessReviewVendorPreference.objects.filter(
        organization=graphql_organization,
        vendor=access_review_testing_vendor,
    ).first()
    alternative_access_review_vendor_preference.refresh_from_db()
    assert (
        access_review_vendor_preference.id
        != alternative_access_review_vendor_preference.id
    )
    assert access_review_vendor_preference.vendor == access_review_testing_vendor
    assert (
        alternative_access_review_vendor_preference.vendor
        == access_review_testing_vendor
    )
    assert list(access_review_vendor_preference.reviewers.all()) == [graphql_user]
    assert list(alternative_access_review_vendor_preference.reviewers.all()) == [
        alternative_organization_stakeholder
    ]


@pytest.mark.functional(
    permissions=['access_review.change_accessreviewvendorpreference']
)
def test_create_access_review_preferences_does_not_deactivate_vendors_in_another_orgs(
    graphql_client,
    graphql_organization,
    access_review_testing_vendor,
    alternative_organization,
):
    create_organization_vendor(graphql_organization, access_review_testing_vendor)
    ar_vendor_preference = create_access_review_vendor_preference(
        organization=graphql_organization,
        vendor=access_review_testing_vendor,
        in_scope=True,
    )
    create_organization_vendor(alternative_organization, access_review_testing_vendor)
    alternative_ar_vendor_preference = create_access_review_vendor_preference(
        organization=alternative_organization,
        vendor=access_review_testing_vendor,
        in_scope=True,
    )
    graphql_client.execute(
        ADD_ACCESS_REVIEW_PREFERENCES,
        variables={
            'input': dict(
                vendorIds=[access_review_testing_vendor.id],
                dueDate='2022-05-09T05:00:00.000Z',
                frequency='quaterly',
            )
        },
    )
    ar_vendor_preference.refresh_from_db()
    alternative_ar_vendor_preference.refresh_from_db()
    assert ar_vendor_preference.in_scope
    assert alternative_ar_vendor_preference.in_scope


@pytest.mark.functional(
    permissions=['access_review.change_accessreviewvendorpreference']
)
def test_update_access_review_vendor_preference_without_modifiying_reviewers(
    graphql_client,
    graphql_organization,
):
    user = graphql_client.context.get('user')
    vendor = create_vendor()
    organization_vendor = create_organization_vendor(graphql_organization, vendor)
    internal_stakeholders = [
        OrganizationVendorStakeholder.objects.create(
            sort_index=index,
            organization_vendor=organization_vendor,
            stakeholder=create_user(
                graphql_organization, email=f'user_{index}@heylaika.com'
            ),
        ).stakeholder
        for index in range(NUMBER_OF_USERS_PER_TEST)
    ]
    organization_vendor.internal_stakeholders.set(internal_stakeholders)
    create_connection_account(
        vendor_name=vendor.name,
        organization=graphql_organization,
        created_by=user,
        vendor=vendor,
    )
    access_review_vendor_preference = create_access_review_vendor_preference(
        organization=graphql_organization,
        vendor=vendor,
        in_scope=True,
        organization_vendor=organization_vendor,
    )
    access_review_vendor_preference.reviewers.set([user])
    graphql_client.execute(
        ADD_ACCESS_REVIEW_PREFERENCES,
        variables={
            'input': dict(
                vendorIds=[vendor.id],
                dueDate='2022-05-09T05:00:00.000Z',
                frequency='quaterly',
            )
        },
    )
    in_scope_vendor = AccessReviewVendorPreference.objects.filter(in_scope=True).first()
    assert list(in_scope_vendor.reviewers.all()) == [user]


@pytest.mark.functional(
    permissions=['access_review.change_accessreviewvendorpreference']
)
@pytest.mark.parametrize(
    'organizations',
    [(['graphql_organization', 'different_organization']), (['graphql_organization'])],
)
def test_change_access_review_preferences_with_multiple_organizations(
    organizations, graphql_organization, graphql_client, connection_account, request
):
    github_run(connection_account)
    vendor = connection_account.integration.vendor
    for organization in organizations:
        org = request.getfixturevalue(organization)
        create_organization_vendor(org, vendor)
    graphql_client.execute(
        ADD_ACCESS_REVIEW_PREFERENCES,
        variables={
            'input': dict(
                vendorIds=['1'],
                dueDate='2022-05-09T05:00:00.000Z',
                frequency='quaterly',
            )
        },
    )
    access_review_preference = AccessReviewPreference.objects.get(
        organization=graphql_organization
    )
    ar_vendor_preference = AccessReviewVendorPreference.objects.filter(in_scope=True)
    assert ar_vendor_preference[0].vendor.id == vendor.id
    assert access_review_preference.frequency == 'quaterly'


@pytest.mark.functional(permissions=['access_review.view_accessreviewpreference'])
@patch('access_review.schema.Q')
def test_return_only_organization_vendors(
    mocked_q, graphql_client, graphql_organization, connection_account
):
    github_run(connection_account)
    user1, _ = users(graphql_organization)
    new_vendor = create_vendor()
    create_connection_account(
        vendor_name=new_vendor.name,
        organization=graphql_organization,
        created_by=user1,
        vendor=new_vendor,
    )
    vendor = connection_account.integration.vendor
    create_organization_vendor(graphql_organization, vendor)
    mocked_q.return_value = Q(id__in=[vendor.id])
    response = graphql_client.execute(GET_ACCESS_REVIEW_PREFERENCES)
    access_review_preferences_response = response['data']['accessReviewPreferences']
    in_scope_vendor = access_review_preferences_response['inScopeVendors']
    assert len(in_scope_vendor) == 1


@pytest.mark.functional(permissions=['access_review.view_accessreviewpreference'])
@patch('access_review.schema.Q')
def test_get_access_review_preference_vendors_empty_whitelist(
    mocked_q,
    graphql_client,
    graphql_organization,
    connection_account,
):
    # Mocking Q instance because UNACCENT function is not supported in sqlite
    mocked_q.return_value = Q(id__in=[])
    github_run(connection_account)
    vendor = connection_account.integration.vendor
    create_access_review_vendor_preference(graphql_organization, vendor)
    response = graphql_client.execute(GET_ACCESS_REVIEW_PREFERENCES)
    access_review_preferences_response = response['data']['accessReviewPreferences']
    in_scope_vendors_list = access_review_preferences_response['inScopeVendors']
    assert len(in_scope_vendors_list) == 0


@pytest.mark.functional(permissions=['access_review.view_accessreviewpreference'])
@patch('access_review.schema.Q')
def test_get_access_review_preference_vendors_whitelisted_only_one(
    mocked_q, graphql_client, new_vendors
):
    vendor_1, _ = new_vendors
    # Mocking Q instance because UNACCENT function is not supported in sqlite
    # here, it is intended to have only the first vendor retrieved by the query
    mocked_q.return_value = Q(id__in=[vendor_1.id])
    response = graphql_client.execute(GET_ACCESS_REVIEW_PREFERENCES)
    access_review_preferences_response = response['data']['accessReviewPreferences']
    in_scope_vendors_list = access_review_preferences_response['inScopeVendors']
    in_scope_vendor = in_scope_vendors_list[0]
    assert len(in_scope_vendors_list) == 1
    assert in_scope_vendor['id'] == str(vendor_1.id)


@pytest.mark.functional(permissions=['access_review.view_accessreviewpreference'])
@patch('access_review.schema.Q')
def test_get_access_review_preference_vendors_whitelisted_both(
    mocked_q, graphql_client, new_vendors
):
    vendor_1, vendor_2 = new_vendors
    # Mocking Q instance because UNACCENT function is not supported in sqlite
    # the returned query must be both of the vendors that will be created
    mocked_q.return_value = Q(id__in=[vendor_1.id, vendor_2.id])
    response = graphql_client.execute(GET_ACCESS_REVIEW_PREFERENCES)
    access_review_preferences_response = response['data']['accessReviewPreferences']
    in_scope_vendors_list = access_review_preferences_response['inScopeVendors']
    in_scope_vendor_whitelisted_ids = set(
        [vendor['id'] for vendor in in_scope_vendors_list]
    )
    assert len(in_scope_vendors_list) == 2
    assert str(vendor_1.id) in in_scope_vendor_whitelisted_ids
    assert str(vendor_2.id) in in_scope_vendor_whitelisted_ids


@pytest.mark.django_db
def test_build_list_vendors_filter(graphql_organization):
    aws_vendor = create_vendor(name='aws')
    create_organization_vendor(graphql_organization, aws_vendor)
    user1, _ = users(graphql_organization)
    create_connection_account(
        vendor_name=aws_vendor.name,
        organization=graphql_organization,
        created_by=user1,
        vendor=aws_vendor,
    )
    vendors_list = build_list_vendors_filter(graphql_organization, dict())
    whitelisted_rendered_vendor_ids = vendors_list.__dict__.get('children', [dict()])[
        0
    ][-1]
    assert aws_vendor.id in whitelisted_rendered_vendor_ids
    assert aws_vendor.id == whitelisted_rendered_vendor_ids[0]


@pytest.mark.functional(permissions=['access_review.view_accessreview'])
def test_get_access_review_help_modal_opened_event_default_value(
    graphql_client, graphql_user, access_review
):
    response = graphql_client.execute(GET_ACCESS_REVIEW)
    access_review_response = response['data']['accessReview']
    assert access_review_response['helpModalOpened'] is False


@pytest.mark.functional(permissions=['access_review.view_accessreview'])
def test_get_access_review_help_modal_event_true_after_open_modal(
    graphql_client, access_review, graphql_user
):
    AccessReviewUserEvent.objects.create(
        access_review=access_review,
        user=graphql_user,
        event=AccessReviewUserEvent.EventType.HELP_MODAL_OPENED,
    )

    final_response = graphql_client.execute(GET_ACCESS_REVIEW)
    final_access_review_response = final_response['data']['accessReview']

    assert final_access_review_response['helpModalOpened'] is True


ADD_ACCESS_REVIEW_EVENT = '''
    mutation addAccessReviewEvent($input: AddAccessReviewEventInput!) {
        addAccessReviewEvent(input: $input) {
            accessReviewUserEvent {
                id
                event
            }
        }
    }
'''


@pytest.mark.functional(
    permissions=[
        'access_review.add_accessreviewuserevent',
        'access_review.view_accessreview',
    ]
)
def test_avoid_access_review_user_entries_duplicate_entries(
    graphql_client, access_review, graphql_user
):
    # Running mutation twice
    response_1 = graphql_client.execute(
        ADD_ACCESS_REVIEW_EVENT,
        variables={
            'input': {
                'id': access_review.id,
                'eventType': AccessReviewUserEvent.EventType.HELP_MODAL_OPENED,
            }
        },
    )
    response_2 = graphql_client.execute(
        ADD_ACCESS_REVIEW_EVENT,
        variables={
            'input': {
                'id': access_review.id,
                'eventType': AccessReviewUserEvent.EventType.HELP_MODAL_OPENED,
            }
        },
    )
    id_1 = response_1['data']['addAccessReviewEvent']['accessReviewUserEvent']['id']
    id_2 = response_2['data']['addAccessReviewEvent']['accessReviewUserEvent']['id']
    assert id_1 == id_2


RUN_VENDOR_INTEGRATIONS = '''
    mutation runVendorIntegrations($vendorId: ID!) {
        runVendorIntegrations(vendorId: $vendorId) {
            taskId
        }
    }
'''


@pytest.mark.functional(permissions=['integration.change_connectionaccount'])
def test_run_vendor_integrations_returns_task_id(
    graphql_client,
    graphql_organization,
):
    vendor = create_vendor(name='aws')
    response = graphql_client.execute(
        RUN_VENDOR_INTEGRATIONS, variables={'vendorId': vendor.id}
    )
    assert response['data']['runVendorIntegrations']['taskId'] is not None


@pytest.mark.functional(permissions=['access_review.view_accessreview'])
@pytest.mark.parametrize(
    'status',
    [
        celery.states.PENDING,
        celery.states.SUCCESS,
        celery.states.FAILURE,
    ],
)
def test_get_vendor_sync_execution_status(graphql_client, status):
    task_result = TaskResult.objects.create(status=status)
    response = graphql_client.execute(
        GET_VENDOR_SYNC_EXECUTION_STATUS,
        variables={'taskResultId': task_result.task_id},
    )
    assert response['data']['vendorSyncExecutionStatus']['status'] == status


GET_VENDOR_SYNC_EXECUTION_STATUS = '''
    query vendorSyncExecutionStatus($taskResultId: ID!) {
        vendorSyncExecutionStatus(taskResultId: $taskResultId) {
            status
        }
    }
'''


@pytest.mark.functional(permissions=['access_review.view_accessreview'])
def test_default_reminder_content(graphql_client, graphql_organization, graphql_user):
    graphql_user.first_name = 'Testing'
    graphql_user.last_name = 'Account'
    graphql_user.save()
    vendor = create_vendor(name='AWS')
    today = date.today()
    create_access_review(graphql_organization, None, due_date=today)
    got = graphql_client.execute(
        GET_DEFAULT_REMINDER_CONTENT, variables={'vendorId': vendor.id}
    )['data']['defaultReminderContent']
    expected = ACCESS_REVIEW_REMINDER.format(
        owner='Testing Account', vendor_name='AWS', due_date=today.strftime('%m/%d/%y')
    )
    assert got == expected


GET_DEFAULT_REMINDER_CONTENT = '''
    query defaultReminderContent($vendorId: ID!) {
        defaultReminderContent(vendorId: $vendorId)
    }
'''

COMPLETE_ACCESS_REVIEW = '''
    mutation completeAccessReview($accessReviewId: ID!) {
        completeAccessReview(accessReviewId: $accessReviewId) {
            accessReview {
                id
                name
                finalReportUrl
            }
        }
    }
'''


@pytest.mark.functional(permissions=['access_review.change_accessreview'])
@pytest.mark.parametrize(
    'frequency, deltatime',
    [
        (AccessReviewPreference.Frequency.MONTHLY, relativedelta(months=1)),
        (AccessReviewPreference.Frequency.QUARTERLY, relativedelta(months=3)),
    ],
)
def test_complete_access_review(
    graphql_client,
    graphql_organization,
    graphql_user,
    access_review_file,
    frequency,
    deltatime,
):
    today = date.today()
    access_review, access_review_preference, _ = setup_complete_access_review(
        access_review_file, graphql_organization, graphql_user, frequency, today
    )

    access_review_user_event = AccessReviewUserEvent.objects.create(
        access_review=access_review,
        user=graphql_user,
        event=AccessReviewUserEvent.EventType.REVIEWED_ACCOUNTS,
    )
    access_review_user_event.access_review_objects.set(AccessReviewObject.objects.all())
    add_control_with_action_item(graphql_organization, 'pending', RECURRENT_ACTION_ITEM)
    action_item = create_action_item(
        name=AR_REVIEWERS_ACTION_ITEM_NAME,
        description=AR_REVIEWERS_ACTION_ITEM_DESCRIPTION,
        due_date=access_review.due_date,
        is_required=True,
        metadata={
            'type': AR_REVIEWERS_ACTION_ITEM_TYPE,
            'accessReviewId': str(access_review.id),
            'organizationId': str(graphql_organization.id),
        },
        status='new',
    )
    response = graphql_client.execute(
        COMPLETE_ACCESS_REVIEW, variables={'accessReviewId': access_review.id}
    )
    action_item.refresh_from_db()
    access_review.refresh_from_db()
    access_review_preference.refresh_from_db()
    final_report_url = response['data']['completeAccessReview']['accessReview'][
        'finalReportUrl'
    ]

    user_events_created = AccessReviewUserEvent.objects.filter(
        access_review=access_review,
        event=AccessReviewUserEvent.EventType.COMPLETE_ACCESS_REVIEW,
    )
    assert action_item.status == ActionItemStatus.COMPLETED
    assert len(user_events_created) == 1
    assert final_report_url
    assert access_review.final_report
    assert access_review.status == AccessReview.Status.DONE
    assert access_review.completed_at is not None
    assert access_review_preference.due_date.date() == today + deltatime
    assert (
        len(
            ActionItem.objects.get(
                metadata__referenceId=RECURRENT_ACTION_ITEM,
                metadata__organizationId=str(graphql_organization.id),
            ).evidences.all()
        )
        == 1
    )


@pytest.mark.functional(permissions=['access_review.change_accessreview'])
def test_complete_access_review_completed_action_item(
    graphql_client, graphql_organization, graphql_user, access_review_file
):
    access_review, _, acv = setup_complete_access_review(
        access_review_file,
        graphql_organization,
        graphql_user,
        AccessReviewPreference.Frequency.MONTHLY,
        date.today(),
    )
    access_review_user_event = AccessReviewUserEvent.objects.create(
        access_review=access_review,
        user=graphql_user,
        event=AccessReviewUserEvent.EventType.REVIEWED_ACCOUNTS,
    )
    access_review_user_event.access_review_objects.set(AccessReviewObject.objects.all())
    add_control_with_action_item(
        graphql_organization, COMPLETED_ACTION_ITEM, RECURRENT_ACTION_ITEM
    )
    create_action_item(
        name=AR_REVIEWERS_ACTION_ITEM_NAME,
        description=AR_REVIEWERS_ACTION_ITEM_DESCRIPTION,
        due_date=access_review.due_date,
        is_required=True,
        metadata={
            'type': AR_REVIEWERS_ACTION_ITEM_TYPE,
            'accessReviewId': str(access_review.id),
            'organizationId': str(graphql_organization.id),
        },
        status='new',
    )
    response = graphql_client.execute(
        COMPLETE_ACCESS_REVIEW, variables={'accessReviewId': access_review.id}
    )
    access_review.refresh_from_db()
    final_report_url = response['data']['completeAccessReview']['accessReview'][
        'finalReportUrl'
    ]
    assert final_report_url
    assert access_review.final_report
    assert (
        len(
            ActionItem.objects.get(
                metadata__referenceId=RECURRENT_ACTION_ITEM,
                metadata__organizationId=str(graphql_organization.id),
            ).evidences.all()
        )
        == 0
    )
    assert (
        len(
            Control.objects.get(
                reference_id=CONTROL_REFERENCE_ID,
                organization_id=graphql_organization.id,
            ).evidence.all()
        )
        == 1
    )


def setup_complete_access_review(
    access_review_file, graphql_organization, graphql_user, frequency, today
):
    access_review = AccessReview.objects.create(
        organization=graphql_organization,
        name='testing_access_review',
        created_by=graphql_user,
    )
    access_review_vendor = create_access_review_vendor(access_review=access_review)
    create_access_review_vendor_preference(
        organization=graphql_organization,
        vendor=access_review_vendor.vendor,
    )
    create_access_review_object(
        graphql_organization,
        access_review=access_review,
        access_review_vendor=access_review_vendor,
        evidence=access_review_file,
    )
    access_review_preference = AccessReviewPreference.objects.create(
        organization=graphql_organization, frequency=frequency, due_date=today
    )
    return access_review, access_review_preference, access_review_vendor


def add_control_with_action_item(
    graphql_organization, action_item_status, reference_id
):
    action_item = create_action_item(
        name='Access Review',
        metadata={
            'referenceId': reference_id,
            'organizationId': str(graphql_organization.id),
        },
        status=action_item_status,
        due_date=date.today(),
    )
    control = create_control(
        organization=graphql_organization,
        display_id=1,
        name='Control Access review',
        description='Testing update control',
        implementation_notes='<p>testing controls</p>',
        reference_id=CONTROL_REFERENCE_ID,
    )
    control.action_items.add(action_item)
    control.save()


ROLE = {'roleName': 'role'}
GROUP = {'groupName': 'group'}


@pytest.mark.functional
@pytest.mark.parametrize(
    'groups, roles, expected',
    [
        (GROUP, None, '{"groupName": "group"}'),
        (None, ROLE, '{"roleName": "role"}'),
        (GROUP, ROLE, '{"groupName": "group"}, {"roleName": "role"}'),
    ],
)
def test_get_laika_object_permissions(groups, roles, expected, graphql_organization):
    laika_object, _ = create_lo_with_connection_account(
        graphql_organization, data={'Roles': roles, 'Groups': groups}
    )
    permissions = get_laika_object_permissions(laika_object)
    assert permissions == expected


@pytest.mark.functional
def test_send_access_review_overdue_emails_overdue(
    graphql_organization, access_review_file
):
    due_date = datetime.today() + timedelta(days=2)
    create_access_review(
        graphql_organization,
        access_review_file,
        AccessReview.Status.IN_PROGRESS,
        due_date,
    )
    result = send_access_review_overdue_emails.delay().get()

    assert result.get('Success') is True
    assert result.get('Emails sent') is True


@pytest.mark.functional
def test_send_access_review_overdue_emails_no_overdue(
    graphql_organization, access_review_file
):
    create_access_review(
        graphql_organization, access_review_file, AccessReview.Status.DONE
    )
    result = send_access_review_overdue_emails.delay().get()

    assert result.get('Success') is True
    assert result.get('Emails sent') is False


@pytest.mark.functional()
def test_get_access_review_tray_keys(
    graphql_client, graphql_organization, graphql_user, access_review_file
):
    access_review, _, acv = setup_complete_access_review(
        access_review_file,
        graphql_organization,
        graphql_user,
        AccessReviewPreference.Frequency.MONTHLY,
        date.today(),
    )
    type_key, description_key, label_key = get_access_review_tray_keys(
        graphql_organization
    )
    assert type_key == ACCESS_REVIEW_TYPE
    assert description_key == ACCESS_REVIEW_ACTION_ITEM_DESCRIPTION_KEY
    assert label_key == ACCESS_REVIEW_CONTINUE_LABEL_KEY


@pytest.mark.functional()
def test_get_access_review_tray_keys_not_in_progress(
    graphql_client, graphql_organization, graphql_user, access_review_file
):
    type_key, description_key, label_key = get_access_review_tray_keys(
        graphql_organization
    )
    assert type_key == ACCESS_REVIEW_TYPE
    assert description_key == ACCESS_REVIEW_ACTION_ITEM_DESCRIPTION_KEY
    assert label_key == ACCESS_REVIEW_START_LABEL_KEY


@pytest.mark.functional
def test_get_access_review_object_updates(graphql_organization, access_review_kwargs):
    access = '"testing", "testing"'
    access_review_kwargs = {
        'review_status': AccessReviewObject.ReviewStatus.UNCHANGED,
        'is_confirmed': True,
        'original_access': access,
        'latest_access': access,
        **access_review_kwargs,
    }
    access_review_object_without_changes = create_access_review_object(
        graphql_organization,
        **access_review_kwargs,
    )
    access_review_object_updated = create_access_review_object(
        graphql_organization,
        **access_review_kwargs,
    )
    access_review_object_updated.latest_access = 'testing'
    laika_object_updated = access_review_object_updated.laika_object
    laika_object_updated.data['Roles'] = 'updated'
    laika_object_updated.save()
    access_review_object_deleted = create_access_review_object(
        graphql_organization,
        **access_review_kwargs,
    )
    laika_object_deleted = access_review_object_deleted.laika_object
    laika_object_deleted.deleted_at = datetime.now()
    laika_object_deleted.save()
    updated_objects, accesses_to_be_reviewed = get_access_review_object_updates(
        [
            access_review_object_without_changes,
            access_review_object_updated,
            access_review_object_deleted,
        ]
    )
    assert updated_objects == {
        str(access_review_object_updated.id): AccessReviewObject.ReviewStatus.MODIFIED,
        str(access_review_object_deleted.id): AccessReviewObject.ReviewStatus.REVOKED,
    }
    assert accesses_to_be_reviewed == {
        str(access_review_object_updated.id),
        str(access_review_object_deleted.id),
    }


@pytest.mark.functional()
def test_check_if_vendor_is_used_by_ongoing_ac_not_used(
    graphql_client, graphql_organization, graphql_user, access_review_file
):
    vendor_name = 'AWS'
    vendor = create_vendor(name=vendor_name, is_public=False)
    access_review, _, acv = setup_complete_access_review(
        access_review_file,
        graphql_organization,
        graphql_user,
        AccessReviewPreference.Frequency.MONTHLY,
        date.today(),
    )
    is_being_used = check_if_vendor_is_used_by_ongoing_ac(
        vendor=vendor, organization=graphql_organization
    )
    assert is_being_used is False


@pytest.mark.functional()
def test_check_if_vendor_is_used_by_ongoing_ac_used(
    graphql_client, graphql_organization, graphql_user, access_review_file
):
    access_review, _, access_review_vendor = setup_complete_access_review(
        access_review_file,
        graphql_organization,
        graphql_user,
        AccessReviewPreference.Frequency.MONTHLY,
        date.today(),
    )
    is_being_used = check_if_vendor_is_used_by_ongoing_ac(
        vendor=access_review_vendor.vendor, organization=graphql_organization
    )
    assert is_being_used is True


@pytest.mark.functional
def test_unselect_in_verdor_preferece_after_connection_is_deleted(
    graphql_organization, graphql_user, access_review_file
):
    connection_1 = access_review_connection_account_setup(
        graphql_organization, graphql_user
    )
    assert len(return_in_scope_vendor_ids(graphql_organization)) == 2
    assert len(return_integrated_vendor_ids(graphql_organization)) == 2
    connection_1.status = ERROR
    connection_1.save()
    validate_in_scope_vendors(graphql_organization)
    assert len(return_in_scope_vendor_ids(graphql_organization)) == 1
    assert len(return_integrated_vendor_ids(graphql_organization)) == 1


def access_review_connection_account_setup(graphql_organization, graphql_user):
    access_review = AccessReview.objects.create(
        organization=graphql_organization,
        name='testing_access_review',
        created_by=graphql_user,
    )
    access_review_vendor = create_access_review_vendor(access_review=access_review)
    access_review_vendor.vendor.name = 'Google Workspace'
    access_review_vendor.vendor.save()
    access_review_vendor2 = create_access_review_vendor(access_review=access_review)
    create_access_review_vendor_preference(
        organization=graphql_organization,
        vendor=access_review_vendor.vendor,
        in_scope=True,
    )
    create_access_review_vendor_preference(
        organization=graphql_organization,
        vendor=access_review_vendor2.vendor,
        in_scope=True,
    )
    connection_1 = create_connection_account(
        'Google Workspace',
        status=SUCCESS,
        created_by=graphql_user,
        organization=graphql_organization,
        vendor=access_review_vendor.vendor,
    )
    create_connection_account(
        'AWS',
        status=SUCCESS,
        created_by=graphql_user,
        organization=graphql_organization,
        vendor=access_review_vendor2.vendor,
    )
    return connection_1

# TODO - REMOVE THIS FILE ON DECEMBER 2023
from datetime import datetime

import pytest
from dateutil.relativedelta import relativedelta

from action_item.models import ActionItem
from alert.constants import ALERT_TYPES
from alert.models import Alert
from control.tasks import (
    FrequencyMapping,
    generate_alert_items,
    generate_recurrent_action_items,
    get_action_item_to_restore_due_date,
    restore_not_created_recurrent_action_items,
)
from control.tests.factory import create_control


def has_parent_action_item_id(action_item: ActionItem):
    assert action_item.parent_action_item is not None


def new_due_date_is_correct(action_item: ActionItem, notice_period):
    assert action_item.due_date == get_action_item_to_restore_due_date(notice_period)


def validate_restored_action_items(notice_period):
    restored_action_items = ActionItem.objects.filter(metadata__is_reviewed=True)

    for action_item in restored_action_items:
        has_parent_action_item_id(action_item)
        new_due_date_is_correct(action_item, notice_period)


def validate_alerts_generated_for_due_date_expiration_coming():
    restored_action_items_with_assignee = ActionItem.objects.filter(
        assignees__isnull=False, metadata__isReviewed=False
    ).values_list('id', flat=True)

    created_alerts = Alert.objects.filter(
        type=ALERT_TYPES['CONTROL_FUTURE_DUE_ACTION_ITEM']
    )

    for alert in created_alerts:
        alert_action_item = alert.action_items.all().first()
        assert alert_action_item.id in restored_action_items_with_assignee


@pytest.fixture
def control_1(graphql_organization):
    return create_control(
        graphql_organization, display_id=1, name='Control 1', reference_id='XX-001-ISO'
    )


@pytest.fixture
def control_2(graphql_organization):
    return create_control(
        graphql_organization, display_id=2, name='Control 2', reference_id='XX-002-SOC'
    )


@pytest.fixture
def weekly_action_items_not_to_be_restored(graphql_organization, control_1):
    due_date = datetime.today()
    weekly_last_overdue_due_date = (
        due_date - FrequencyMapping.WEEKLY.value.notice_period
    )

    action_items_metadata = [
        {
            'is_recurrent': True,
            'recurrent_schedule': FrequencyMapping.WEEKLY.value.name,
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AW-R-010',
        },
        {
            'is_recurrent': True,
            'recurrent_schedule': FrequencyMapping.WEEKLY.value.name,
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AW-R-011',
        },
        {
            'is_recurrent': True,
            'recurrent_schedule': FrequencyMapping.WEEKLY.value.name,
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AW-R-012',
        },
    ]

    days_not_in_a_weekly_sequence = [25, 33, 91]

    weekly_action_item_1 = ActionItem.objects.create(
        name='Weekly action item, not to be restored',
        due_date=weekly_last_overdue_due_date
        - relativedelta(days=days_not_in_a_weekly_sequence[0]),
    )
    weekly_action_item_2 = ActionItem.objects.create(
        name='Weekly action item, not to be restored',
        due_date=weekly_last_overdue_due_date
        - relativedelta(days=days_not_in_a_weekly_sequence[1]),
    )
    weekly_action_item_3 = ActionItem.objects.create(
        name='Weekly action item, not to be restored',
        due_date=weekly_last_overdue_due_date
        - relativedelta(days=days_not_in_a_weekly_sequence[2]),
    )

    weekly_action_item_1.metadata = action_items_metadata[0]
    weekly_action_item_2.metadata = action_items_metadata[1]
    weekly_action_item_3.metadata = action_items_metadata[2]

    weekly_action_item_1.save()
    weekly_action_item_2.save()
    weekly_action_item_3.save()

    control_1.action_items.add(
        weekly_action_item_1, weekly_action_item_2, weekly_action_item_3
    )


@pytest.fixture
def monthly_action_items_not_to_be_restored(graphql_organization, control_2):
    due_date = datetime.today()
    monthly_last_overdue_due_date = (
        due_date - FrequencyMapping.MONTHLY.value.notice_period
    )

    action_items_metadata = [
        {
            'is_recurrent': True,
            'recurrent_schedule': FrequencyMapping.MONTHLY.value.name,
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AM-R-010',
        },
        {
            'is_recurrent': True,
            'recurrent_schedule': FrequencyMapping.MONTHLY.value.name,
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AM-R-011',
        },
        {
            'is_recurrent': True,
            'recurrent_schedule': FrequencyMapping.MONTHLY.value.name,
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AM-R-012',
        },
    ]

    days_not_in_a_monthly_sequence = [20, 45, 70]

    monthly_action_item_1 = ActionItem.objects.create(
        name='Monthly action item, not to be restored',
        due_date=monthly_last_overdue_due_date
        - relativedelta(days=days_not_in_a_monthly_sequence[0]),
    )
    monthly_action_item_2 = ActionItem.objects.create(
        name='Monthly action item, not to be restored',
        due_date=monthly_last_overdue_due_date
        - relativedelta(days=days_not_in_a_monthly_sequence[1]),
    )
    monthly_action_item_3 = ActionItem.objects.create(
        name='Monthly action item, not to be restored',
        due_date=monthly_last_overdue_due_date
        - relativedelta(days=days_not_in_a_monthly_sequence[2]),
    )

    monthly_action_item_1.metadata = action_items_metadata[0]
    monthly_action_item_2.metadata = action_items_metadata[1]
    monthly_action_item_3.metadata = action_items_metadata[2]

    monthly_action_item_1.save()
    monthly_action_item_2.save()
    monthly_action_item_3.save()

    control_2.action_items.add(
        monthly_action_item_1, monthly_action_item_2, monthly_action_item_3
    )


@pytest.fixture
def quarterly_action_items_not_to_be_restored(graphql_organization, control_1):
    due_date = datetime.today()
    quarterly_last_overdue_due_date = (
        due_date - FrequencyMapping.QUARTERLY.value.notice_period
    )

    action_items_metadata = [
        {
            'is_recurrent': True,
            'recurrent_schedule': FrequencyMapping.QUARTERLY.value.name,
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AQ-R-010',
        },
        {
            'is_recurrent': True,
            'recurrent_schedule': FrequencyMapping.QUARTERLY.value.name,
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AQ-R-011',
        },
        {
            'is_recurrent': True,
            'recurrent_schedule': FrequencyMapping.QUARTERLY.value.name,
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AQ-R-012',
        },
    ]

    days_not_in_a_quarterly_sequence = [10, 50, 100]

    quarterly_action_item_1 = ActionItem.objects.create(
        name='Monthly action item, not to be restored',
        due_date=quarterly_last_overdue_due_date
        - relativedelta(days=days_not_in_a_quarterly_sequence[0]),
    )
    quarterly_action_item_2 = ActionItem.objects.create(
        name='Monthly action item, not to be restored',
        due_date=quarterly_last_overdue_due_date
        - relativedelta(days=days_not_in_a_quarterly_sequence[1]),
    )
    quarterly_action_item_3 = ActionItem.objects.create(
        name='Monthly action item, not to be restored',
        due_date=quarterly_last_overdue_due_date
        - relativedelta(days=days_not_in_a_quarterly_sequence[2]),
    )

    quarterly_action_item_1.metadata = action_items_metadata[0]
    quarterly_action_item_2.metadata = action_items_metadata[1]
    quarterly_action_item_3.metadata = action_items_metadata[2]

    quarterly_action_item_1.save()
    quarterly_action_item_2.save()
    quarterly_action_item_3.save()

    control_1.action_items.add(
        quarterly_action_item_1, quarterly_action_item_2, quarterly_action_item_3
    )


@pytest.fixture
def semi_annually_action_items_not_to_be_restored(graphql_organization, control_2):
    due_date = datetime.today()
    semi_annually_last_overdue_due_date = (
        due_date - FrequencyMapping.SEMI_ANNUALLY.value.notice_period
    )

    action_items_metadata = [
        {
            'is_recurrent': True,
            'recurrent_schedule': FrequencyMapping.SEMI_ANNUALLY.value.name,
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AS-R-010',
        },
        {
            'is_recurrent': True,
            'recurrent_schedule': FrequencyMapping.SEMI_ANNUALLY.value.name,
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AS-R-011',
        },
        {
            'is_recurrent': True,
            'recurrent_schedule': FrequencyMapping.SEMI_ANNUALLY.value.name,
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AS-R-012',
        },
    ]

    days_not_in_a_semi_annually_sequence = [30, 60, 100]

    quarterly_action_item_1 = ActionItem.objects.create(
        name='Monthly action item, not to be restored',
        due_date=semi_annually_last_overdue_due_date
        - relativedelta(days=days_not_in_a_semi_annually_sequence[0]),
    )
    quarterly_action_item_2 = ActionItem.objects.create(
        name='Monthly action item, not to be restored',
        due_date=semi_annually_last_overdue_due_date
        - relativedelta(days=days_not_in_a_semi_annually_sequence[1]),
    )
    quarterly_action_item_3 = ActionItem.objects.create(
        name='Monthly action item, not to be restored',
        due_date=semi_annually_last_overdue_due_date
        - relativedelta(days=days_not_in_a_semi_annually_sequence[2]),
    )

    quarterly_action_item_1.metadata = action_items_metadata[0]
    quarterly_action_item_2.metadata = action_items_metadata[1]
    quarterly_action_item_3.metadata = action_items_metadata[2]

    quarterly_action_item_1.save()
    quarterly_action_item_2.save()
    quarterly_action_item_3.save()

    control_2.action_items.add(
        quarterly_action_item_1, quarterly_action_item_2, quarterly_action_item_3
    )


@pytest.fixture
def annually_action_items_not_to_be_restored(graphql_organization, control_1):
    due_date = datetime.today()
    annually_last_overdue_due_date = (
        due_date - FrequencyMapping.ANNUALLY.value.notice_period
    )

    action_items_metadata = [
        {
            'is_recurrent': True,
            'recurrent_schedule': FrequencyMapping.ANNUALLY.value.name,
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AS-R-010',
        },
        {
            'is_recurrent': True,
            'recurrent_schedule': FrequencyMapping.ANNUALLY.value.name,
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AS-R-011',
        },
        {
            'is_recurrent': True,
            'recurrent_schedule': FrequencyMapping.ANNUALLY.value.name,
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AS-R-012',
        },
    ]

    days_not_in_a_annually_sequence = [40, 120, 200]

    quarterly_action_item_1 = ActionItem.objects.create(
        name='Monthly action item, not to be restored',
        due_date=annually_last_overdue_due_date
        - relativedelta(days=days_not_in_a_annually_sequence[0]),
    )
    quarterly_action_item_2 = ActionItem.objects.create(
        name='Monthly action item, not to be restored',
        due_date=annually_last_overdue_due_date
        - relativedelta(days=days_not_in_a_annually_sequence[1]),
    )
    quarterly_action_item_3 = ActionItem.objects.create(
        name='Monthly action item, not to be restored',
        due_date=annually_last_overdue_due_date
        - relativedelta(days=days_not_in_a_annually_sequence[2]),
    )

    quarterly_action_item_1.metadata = action_items_metadata[0]
    quarterly_action_item_2.metadata = action_items_metadata[1]
    quarterly_action_item_3.metadata = action_items_metadata[2]

    quarterly_action_item_1.save()
    quarterly_action_item_2.save()
    quarterly_action_item_3.save()

    control_1.action_items.add(
        quarterly_action_item_1, quarterly_action_item_2, quarterly_action_item_3
    )


@pytest.fixture
def weekly_action_items(graphql_organization, graphql_user, control_1):
    due_date = datetime.today()
    common_properties = {
        'is_recurrent': True,
        'recurrent_schedule': FrequencyMapping.WEEKLY.value.name,
    }
    action_items_metadata = [
        {
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AW-R-001',
        },
        {
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AW-R-002',
        },
        {
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AW-R-003',
        },
        {
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AW-R-004',
        },
    ]

    last_overdue_due_date = due_date - FrequencyMapping.WEEKLY.value.notice_period
    initial_overdue_due_date = last_overdue_due_date - relativedelta(weeks=53)

    last_action_item_expired = ActionItem.objects.create(
        name='Last expired action item',
        due_date=last_overdue_due_date,
        **common_properties,
    )
    action_item_expired_26_weeks_ago = ActionItem.objects.create(
        name='Action item expired 26 weeks ago',
        due_date=last_overdue_due_date - relativedelta(weeks=26),
        **common_properties,
    )
    action_item_expired_40_weeks_ago = ActionItem.objects.create(
        name='Action item expired 40 weeks ago',
        due_date=last_overdue_due_date - relativedelta(weeks=40),
        **common_properties,
    )
    first_action_item_expired = ActionItem.objects.create(
        name='First expired action item',
        due_date=initial_overdue_due_date,
        **common_properties,
    )

    last_action_item_expired.metadata = action_items_metadata[0]
    action_item_expired_26_weeks_ago.metadata = action_items_metadata[1]
    action_item_expired_40_weeks_ago.metadata = action_items_metadata[2]
    first_action_item_expired.metadata = action_items_metadata[3]

    last_action_item_expired.save()
    action_item_expired_26_weeks_ago.save()
    action_item_expired_40_weeks_ago.save()
    first_action_item_expired.save()

    last_action_item_expired.assignees.set([graphql_user])

    # Link action items with control_1
    control_1.action_items.add(
        last_action_item_expired,
        action_item_expired_26_weeks_ago,
        action_item_expired_40_weeks_ago,
        first_action_item_expired,
    )


@pytest.fixture
def monthly_action_items(graphql_organization, graphql_user, control_2):
    due_date = datetime.today()
    common_properties = {
        'is_recurrent': True,
        'recurrent_schedule': FrequencyMapping.MONTHLY.value.name,
    }
    action_items_metadata = [
        {
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AM-R-001',
        },
        {
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AM-R-002',
        },
        {
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AM-R-003',
        },
        {
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AM-R-004',
        },
    ]

    last_overdue_due_date = due_date - FrequencyMapping.MONTHLY.value.notice_period
    initial_overdue_due_date = last_overdue_due_date - relativedelta(months=12)

    last_action_item_expired = ActionItem.objects.create(
        name='Last expired action item',
        due_date=last_overdue_due_date,
        **common_properties,
    )
    action_item_expired_5_months_ago = ActionItem.objects.create(
        name='Action item expired 5 months ago',
        due_date=last_overdue_due_date - relativedelta(months=5),
        **common_properties,
    )
    action_item_expired_10_months_ago = ActionItem.objects.create(
        name='Action item expired 10 months ago',
        due_date=last_overdue_due_date - relativedelta(months=10),
        **common_properties,
    )
    first_action_item_expired = ActionItem.objects.create(
        name='First expired action item',
        due_date=initial_overdue_due_date,
        **common_properties,
    )

    last_action_item_expired.metadata = action_items_metadata[0]
    action_item_expired_5_months_ago.metadata = action_items_metadata[1]
    action_item_expired_10_months_ago.metadata = action_items_metadata[2]
    first_action_item_expired.metadata = action_items_metadata[3]

    last_action_item_expired.save()
    action_item_expired_5_months_ago.save()
    action_item_expired_10_months_ago.save()
    first_action_item_expired.save()

    last_action_item_expired.assignees.set([graphql_user])
    first_action_item_expired.assignees.set([graphql_user])

    # Link action items with control_2
    control_2.action_items.add(
        last_action_item_expired,
        action_item_expired_5_months_ago,
        action_item_expired_10_months_ago,
        first_action_item_expired,
    )


@pytest.fixture
def quarterly_action_items(graphql_organization, graphql_user, control_1):
    due_date = datetime.today()
    common_properties = {
        'is_recurrent': True,
        'recurrent_schedule': FrequencyMapping.QUARTERLY.value.name,
    }
    action_items_metadata = [
        {
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AQ-R-001',
        },
        {
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AQ-R-002',
        },
        {
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AQ-R-003',
        },
        {
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AQ-R-004',
        },
    ]

    last_overdue_due_date = due_date - FrequencyMapping.QUARTERLY.value.notice_period
    initial_overdue_due_date = last_overdue_due_date - relativedelta(months=12)

    last_action_item_expired = ActionItem.objects.create(
        name='Last expired action item',
        due_date=last_overdue_due_date,
        **common_properties,
    )
    action_item_expired_2_quarters_ago = ActionItem.objects.create(
        name='Action item expired 6 months ago',
        due_date=last_overdue_due_date - relativedelta(months=6),
        **common_properties,
    )
    action_item_expired_3_quarters_ago = ActionItem.objects.create(
        name='Action item expired 9 months ago',
        due_date=last_overdue_due_date - relativedelta(months=9),
        **common_properties,
    )
    first_action_item_expired = ActionItem.objects.create(
        name='First expired action item',
        due_date=initial_overdue_due_date,
        **common_properties,
    )

    last_action_item_expired.metadata = action_items_metadata[0]
    action_item_expired_2_quarters_ago.metadata = action_items_metadata[1]
    action_item_expired_3_quarters_ago.metadata = action_items_metadata[2]
    first_action_item_expired.metadata = action_items_metadata[3]

    last_action_item_expired.save()
    action_item_expired_2_quarters_ago.save()
    action_item_expired_3_quarters_ago.save()
    first_action_item_expired.save()

    last_action_item_expired.assignees.set([graphql_user])
    action_item_expired_2_quarters_ago.assignees.set([graphql_user])
    action_item_expired_3_quarters_ago.assignees.set([graphql_user])

    # Link action items with control_1
    control_1.action_items.add(
        last_action_item_expired,
        action_item_expired_2_quarters_ago,
        action_item_expired_3_quarters_ago,
        first_action_item_expired,
    )


@pytest.fixture
def semi_annually_action_items(graphql_organization, graphql_user, control_2):
    due_date = datetime.today()
    common_properties = {
        'is_recurrent': True,
        'recurrent_schedule': FrequencyMapping.SEMI_ANNUALLY.value.name,
    }
    action_items_metadata = [
        {
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AS-R-001',
        },
        {
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AS-R-002',
        },
        {
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AS-R-003',
        },
    ]

    last_overdue_due_date = (
        due_date - FrequencyMapping.SEMI_ANNUALLY.value.notice_period
    )
    initial_overdue_due_date = last_overdue_due_date - relativedelta(months=12)

    last_action_item_expired = ActionItem.objects.create(
        name='Last expired action item',
        due_date=last_overdue_due_date,
        **common_properties,
    )
    action_item_expired_6_months_ago = ActionItem.objects.create(
        name='Action item expired 6 months ago',
        due_date=last_overdue_due_date - relativedelta(months=6),
        **common_properties,
    )
    first_action_item_expired = ActionItem.objects.create(
        name='First expired action item',
        due_date=initial_overdue_due_date,
        **common_properties,
    )

    last_action_item_expired.metadata = action_items_metadata[0]
    action_item_expired_6_months_ago.metadata = action_items_metadata[1]
    first_action_item_expired.metadata = action_items_metadata[2]

    last_action_item_expired.save()
    action_item_expired_6_months_ago.save()
    first_action_item_expired.save()

    last_action_item_expired.assignees.set([graphql_user])

    # Link action items with control_2
    control_2.action_items.add(
        last_action_item_expired,
        action_item_expired_6_months_ago,
        first_action_item_expired,
    )


@pytest.fixture
def annually_action_items(graphql_organization, graphql_user, control_1):
    due_date = datetime.today()
    common_properties = {
        'is_recurrent': True,
        'recurrent_schedule': FrequencyMapping.ANNUALLY.value.name,
    }
    action_items_metadata = [
        {
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AA-R-001',
        },
        {
            'type': 'control',
            'isReviewed': False,
            'organizationId': str(graphql_organization.id),
            'referenceId': 'AA-R-002',
        },
    ]

    last_overdue_due_date = due_date - FrequencyMapping.ANNUALLY.value.notice_period
    initial_overdue_due_date = last_overdue_due_date - relativedelta(years=1)

    last_action_item_expired = ActionItem.objects.create(
        name='Last expired action item',
        due_date=last_overdue_due_date,
        **common_properties,
    )
    first_action_item_expired = ActionItem.objects.create(
        name='First expired action item',
        due_date=initial_overdue_due_date,
        **common_properties,
    )

    last_action_item_expired.metadata = action_items_metadata[0]
    first_action_item_expired.metadata = action_items_metadata[1]

    last_action_item_expired.save()
    first_action_item_expired.save()

    last_action_item_expired.assignees.set([graphql_user])

    # Link action items with control_1
    control_1.action_items.add(last_action_item_expired, first_action_item_expired)


@pytest.mark.django_db
def test_restore_weekly_overdue_action_items(
    weekly_action_items, weekly_action_items_not_to_be_restored
):
    response = restore_not_created_recurrent_action_items()
    expected_weekly_action_items_response = (
        "Restored action items: 4. "
        + "Failed to restore action items: 0. "
        + "Failed to restore action item IDs: []."
    )

    validate_restored_action_items(FrequencyMapping.WEEKLY.value.notice_period)
    assert response == expected_weekly_action_items_response


@pytest.mark.django_db
def test_restore_monthly_overdue_action_items(
    monthly_action_items, monthly_action_items_not_to_be_restored
):
    response = restore_not_created_recurrent_action_items()
    expected_monthly_action_items_response = (
        "Restored action items: 4. "
        + "Failed to restore action items: 0. "
        + "Failed to restore action item IDs: []."
    )

    validate_restored_action_items(FrequencyMapping.MONTHLY.value.notice_period)
    assert response == expected_monthly_action_items_response


@pytest.mark.django_db
def test_restore_quarterly_overdue_action_items(
    quarterly_action_items, quarterly_action_items_not_to_be_restored
):
    response = restore_not_created_recurrent_action_items()
    expected_quarterly_action_items_response = (
        "Restored action items: 4. "
        + "Failed to restore action items: 0. "
        + "Failed to restore action item IDs: []."
    )

    validate_restored_action_items(FrequencyMapping.QUARTERLY.value.notice_period)
    assert response == expected_quarterly_action_items_response


@pytest.mark.django_db
def test_restore_semi_annually_overdue_action_items(
    semi_annually_action_items, semi_annually_action_items_not_to_be_restored
):
    response = restore_not_created_recurrent_action_items()
    expected_semi_annually_action_items_response = (
        "Restored action items: 3. "
        + "Failed to restore action items: 0. "
        + "Failed to restore action item IDs: []."
    )

    validate_restored_action_items(FrequencyMapping.SEMI_ANNUALLY.value.notice_period)
    assert response == expected_semi_annually_action_items_response


@pytest.mark.django_db
def test_restore_annually_overdue_action_items(
    annually_action_items, annually_action_items_not_to_be_restored
):
    response = restore_not_created_recurrent_action_items()
    expected_annually_action_items_response = (
        "Restored action items: 2. "
        + "Failed to restore action items: 0. "
        + "Failed to restore action item IDs: []."
    )

    validate_restored_action_items(FrequencyMapping.ANNUALLY.value.notice_period)
    assert response == expected_annually_action_items_response


@pytest.mark.django_db
def test_generate_weekly_action_item_and_restore_not_created_weekly_action_items(
    weekly_action_items,
):
    # Test the case where the job is executed and there is one action item
    # 5 days (weekly notice period) behind the current day and the rest of
    # the action items are the ones to restore.

    # The job executes first the creation, then the restoration,
    # that's why the test simulates the same execution order.
    action_item_creation_response = generate_recurrent_action_items()
    action_item_restoration_response = restore_not_created_recurrent_action_items()

    expected_creation_response = (
        "Created action items: 1. Failed action items: 0. Failed action item IDs: []."
    )
    expected_restoration_response = (
        "Restored action items: 3. "
        + "Failed to restore action items: 0. "
        + "Failed to restore action item IDs: []."
    )

    validate_restored_action_items(FrequencyMapping.WEEKLY.value.notice_period)
    assert action_item_creation_response == expected_creation_response
    assert action_item_restoration_response == expected_restoration_response


@pytest.mark.django_db
def test_generate_monthly_action_item_and_restore_not_created_monthly_action_items(
    monthly_action_items,
):
    # Test the case where the job is executed and there is one action item
    # roughly 3 weeks (monthly notice period) behind the current day and the rest of
    # the action items are the ones to restore.

    # The job executes first the creation, then the restoration,
    # that's why the test simulates the same execution order.
    action_item_creation_response = generate_recurrent_action_items()
    action_item_restoration_response = restore_not_created_recurrent_action_items()

    expected_creation_response = (
        "Created action items: 1. Failed action items: 0. Failed action item IDs: []."
    )
    expected_restoration_response = (
        "Restored action items: 3. "
        + "Failed to restore action items: 0. "
        + "Failed to restore action item IDs: []."
    )

    validate_restored_action_items(FrequencyMapping.MONTHLY.value.notice_period)
    assert action_item_creation_response == expected_creation_response
    assert action_item_restoration_response == expected_restoration_response


@pytest.mark.django_db
def test_generate_quarterly_action_item_and_restore_not_created_quarterly_action_items(
    quarterly_action_items,
):
    # Test the case where the job is executed and there is one action item
    # roughly 11 weeks (quarterly notice period) behind the current day and the rest of
    # the action items are the ones to restore.

    # The job executes first the creation, then the restoration,
    # that's why the test simulates the same execution order.
    action_item_creation_response = generate_recurrent_action_items()
    action_item_restoration_response = restore_not_created_recurrent_action_items()

    expected_creation_response = (
        "Created action items: 1. Failed action items: 0. Failed action item IDs: []."
    )
    expected_restoration_response = (
        "Restored action items: 3. "
        + "Failed to restore action items: 0. "
        + "Failed to restore action item IDs: []."
    )

    validate_restored_action_items(FrequencyMapping.QUARTERLY.value.notice_period)
    assert action_item_creation_response == expected_creation_response
    assert action_item_restoration_response == expected_restoration_response


@pytest.mark.django_db
def test_generate_semi_annually_and_restore_not_created_semi_annually_action_items(
    semi_annually_action_items,
):
    # Test the case where the job is executed and there is one action item
    # roughly 5 months (semi_annually notice period) behind the current day
    # and the rest of the action items are the ones to restore.

    # The job executes first the creation, then the restoration,
    # that's why the test simulates the same execution order.
    action_item_creation_response = generate_recurrent_action_items()
    action_item_restoration_response = restore_not_created_recurrent_action_items()

    expected_creation_response = (
        "Created action items: 1. Failed action items: 0. Failed action item IDs: []."
    )
    expected_restoration_response = (
        "Restored action items: 2. "
        + "Failed to restore action items: 0. "
        + "Failed to restore action item IDs: []."
    )

    validate_restored_action_items(FrequencyMapping.SEMI_ANNUALLY.value.notice_period)
    assert action_item_creation_response == expected_creation_response
    assert action_item_restoration_response == expected_restoration_response


@pytest.mark.django_db
def test_generate_annually_action_item_and_restore_not_created_annually_action_items(
    annually_action_items,
):
    # Test the case where the job is executed and there is one action item
    # roughly 11 months (annually notice period) behind the current day and the rest of
    # the action items are the ones to restore.

    # The job executes first the creation, then the restoration,
    # that's why the test simulates the same execution order.
    action_item_creation_response = generate_recurrent_action_items()
    action_item_restoration_response = restore_not_created_recurrent_action_items()

    expected_creation_response = (
        "Created action items: 1. Failed action items: 0. Failed action item IDs: []."
    )
    expected_restoration_response = (
        "Restored action items: 1. "
        + "Failed to restore action items: 0. "
        + "Failed to restore action item IDs: []."
    )

    validate_restored_action_items(FrequencyMapping.ANNUALLY.value.notice_period)
    assert action_item_creation_response == expected_creation_response
    assert action_item_restoration_response == expected_restoration_response


@pytest.mark.django_db
def test_restore_weekly_action_items_and_generate_alert_advance_of_due_date(
    weekly_action_items,
):
    # Test case where weekly action items are restored and then an alert
    # is generated to let the user know 2 days in advance about the due date expiration.
    # Alert is generated just for the action items with assignee.

    # The job executes first the restoration, then the alert's generation,
    # that's why the test simulates the same execution order.
    restore_not_created_recurrent_action_items()
    generate_alert_items()

    validate_restored_action_items(FrequencyMapping.WEEKLY.value.notice_period)
    validate_alerts_generated_for_due_date_expiration_coming()


@pytest.mark.django_db
def test_restore_monthly_action_items_and_generate_alert_advance_of_due_date(
    monthly_action_items,
):
    # Test case where monthly action items are restored and then an alert
    # is generated to let the user know 7 days in advance about the due date expiration.
    # Alert is generated just for the action items with assignee.

    # The job executes first the restoration, then the alert's generation,
    # that's why the test simulates the same execution order.
    restore_not_created_recurrent_action_items()
    generate_alert_items()

    validate_restored_action_items(FrequencyMapping.MONTHLY.value.notice_period)
    validate_alerts_generated_for_due_date_expiration_coming()


@pytest.mark.django_db
def test_restore_quarterly_action_items_and_generate_alert_advance_of_due_date(
    quarterly_action_items,
):
    # Test case where quarterly action items are restored and then an alert
    # is generated to let the user know 7 days in advance about the due date expiration.
    # Alert is generated just for the action items with assignee.

    # The job executes first the restoration, then the alert's generation,
    # that's why the test simulates the same execution order.
    restore_not_created_recurrent_action_items()
    generate_alert_items()

    validate_restored_action_items(FrequencyMapping.QUARTERLY.value.notice_period)
    validate_alerts_generated_for_due_date_expiration_coming()


@pytest.mark.django_db
def test_restore_semi_annually_action_items_and_generate_alert_advance_of_due_date(
    semi_annually_action_items,
):
    # Test case where semi-annually action items are restored and then an alert
    # is generated to let the user know 30 days in advance about the due
    # date expiration. Alert is generated just for the action items with assignee.

    # The job executes first the restoration, then the alert's generation,
    # that's why the test simulates the same execution order.
    restore_not_created_recurrent_action_items()
    generate_alert_items()

    validate_restored_action_items(FrequencyMapping.SEMI_ANNUALLY.value.notice_period)
    validate_alerts_generated_for_due_date_expiration_coming()


@pytest.mark.django_db
def test_restore_annually_action_items_and_generate_alert_advance_of_due_date(
    annually_action_items,
):
    # Test case where annually action items are restored and then an alert
    # is generated to let the user know 30 days in advance about the due
    # date expiration. Alert is generated just for the action items with
    # assignee.

    # The job executes first the restoration, then the alert's generation,
    # that's why the test simulates the same execution order.
    restore_not_created_recurrent_action_items()
    generate_alert_items()

    validate_restored_action_items(FrequencyMapping.ANNUALLY.value.notice_period)
    validate_alerts_generated_for_due_date_expiration_coming()

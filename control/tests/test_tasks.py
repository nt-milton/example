from copy import deepcopy
from datetime import datetime
from typing import List

import pytest
from dateutil.relativedelta import relativedelta

from action_item.models import ActionItem, ActionItemStatus
from alert.constants import ALERT_TYPES
from alert.models import Alert
from control.constants import CONTROL_TYPE, MetadataFields
from control.tasks import (
    CONTROL_ACTION_ITEM_TYPE,
    FrequencyMapping,
    generate_alert_items,
    generate_recurrent_action_items,
)
from control.tests.test_control_action_items import fixture_action_item  # noqa: F401
from control.tests.test_control_action_items import fixture_control  # noqa: F401

RECURRENT_1 = 'XX-R-001'


def copy_action_item(_action_item, index, date, period, is_recurrent, assignees=None):
    new_action_item = deepcopy(_action_item)
    new_action_item.id = index
    new_action_item.name = F"RAI-00{index}"
    new_action_item.due_date = date
    new_action_item.is_recurrent = is_recurrent
    new_action_item.recurrent_schedule = period

    if new_action_item.assignees.first() and not assignees:
        new_action_item.assignees.remove(new_action_item.assignees.first())

    if assignees:
        new_action_item.assignees.set(assignees)

    new_action_item.save()

    return new_action_item


def create_policy_action_item(action_item, index):
    policy_action_item = deepcopy(action_item)
    policy_action_item.id = index
    policy_action_item.metadata['type'] = 'policy'
    policy_action_item.save()


def create_action_item_without_type_field(action_item, index):
    action_item_without_type = deepcopy(action_item)
    action_item_without_type.id = index
    action_item_without_type.metadata['type'] = ''
    action_item_without_type.save()


@pytest.fixture(autouse=True)
def set_up_test(graphql_user, _control, _action_item):  # noqa: F811
    _control.action_items.add(_action_item)
    _action_item.assignees.add(graphql_user)


@pytest.mark.functional()
@pytest.mark.parametrize(
    'frequency_mapping',
    [freq for freq in FrequencyMapping if freq is not FrequencyMapping.IMMEDIATELY],
)
def test_success_generate_recurrent_action_items(
    _action_item, frequency_mapping  # noqa: F811
):
    # Given
    _action_item.name = 'RAI-001'
    _action_item.is_recurrent = True
    _action_item.is_required = True
    _action_item.recurrent_schedule = frequency_mapping.value.name
    _action_item.metadata[MetadataFields.IS_REVIEWED.value] = False
    _action_item.metadata[MetadataFields.REFERENCE_ID.value] = RECURRENT_1
    _action_item.due_date = datetime.today()

    if frequency_mapping.value.notice_period:
        _action_item.due_date -= frequency_mapping.value.notice_period

    _action_item.save()

    # When
    report = generate_recurrent_action_items()

    # Then
    assert ActionItem.objects.count() == 2
    assert ActionItem.objects.filter(name="RAI-001").count() == 2

    recurrent_action_items = ActionItem.objects.filter(
        metadata__referenceId=RECURRENT_1
    ).order_by('due_date')

    rai_001 = recurrent_action_items[0]
    rai_002 = recurrent_action_items[1]

    assert rai_001.metadata[
        MetadataFields.IS_REVIEWED.value
    ], "Initial action item must be mark as reviewed"

    assert rai_002.metadata.get(MetadataFields.REFERENCE_ID) == rai_001.metadata.get(
        MetadataFields.REFERENCE_ID
    )

    assert (
        rai_002.due_date.date()
        == (_action_item.due_date + frequency_mapping.value.duration).date()
    )
    assert rai_001.due_date < rai_002.due_date

    assert (
        MetadataFields.IS_REVIEWED.value in rai_002.metadata
    ), f"New LAI must contain a metadata field '{MetadataFields.IS_REVIEWED.value}'"
    assert rai_002.metadata[MetadataFields.IS_REVIEWED.value] is False
    assert rai_002.metadata[MetadataFields.TYPE.value] == CONTROL_TYPE

    assert rai_002.status == ActionItemStatus.NEW
    assert rai_002.description == rai_001.description
    assert rai_002.is_required is False, "Created RAI must not be required"
    assert rai_002.is_recurrent == rai_001.is_recurrent
    assert rai_002.recurrent_schedule == rai_001.recurrent_schedule

    for user in rai_002.assignees.all():
        assert user in rai_001.assignees.all()

    for control in rai_002.controls.all():
        assert control in rai_001.controls.all()
        assert control.has_new_action_items

    _validate_report(report=report, created_lai=1)


@pytest.mark.functional()
def test_generate_recurrent_action_items_skip_already_processed(
    _action_item,
):  # noqa: F811
    # Given: an action item that was marked as reviewed
    _action_item.name = "RAI-001"
    _action_item.is_recurrent = True
    _action_item.recurrent_schedule = FrequencyMapping.WEEKLY.value.name
    _action_item.due_date = datetime.today()
    _action_item.metadata[MetadataFields.IS_REVIEWED.value] = True
    _action_item.save()

    # When
    report = generate_recurrent_action_items()

    # Then: new action item must not be created
    assert ActionItem.objects.count() == 1

    rai_001 = ActionItem.objects.get(name="RAI-001")
    assert rai_001.metadata[MetadataFields.IS_REVIEWED.value]

    assert ActionItem.objects.filter(name="RAI-002").count() == 0

    _validate_report(report=report)


@pytest.mark.functional()
def test_generate_recurrent_action_items_only_recurrent_processed(
    _action_item,
):  # noqa: F811
    _action_item.recurrent_schedule = ''
    _action_item.save()
    # When
    report = generate_recurrent_action_items()

    # Then: action item must be left intact
    _validate_report(report=report)

    assert ActionItem.objects.count() == 1

    lai_001 = ActionItem.objects.get(name=_action_item.name)
    assert MetadataFields.IS_REVIEWED.value not in lai_001.metadata


@pytest.mark.functional()
def test_failed_generate_recurrent_action_items(_action_item):  # noqa: F811
    # Given
    _action_item.name = ''
    _action_item.metadata[MetadataFields.REFERENCE_ID.value] = ''
    _action_item.due_date -= FrequencyMapping.WEEKLY.value.notice_period
    _action_item.recurrent_schedule = FrequencyMapping.WEEKLY.value.name
    _action_item.metadata[MetadataFields.IS_REVIEWED.value] = False
    _action_item.save()

    # When
    report = generate_recurrent_action_items()

    # Then
    _validate_report(report=report, failed_lai=1, failed_lai_ids=[_action_item.id])


def _validate_report(
    report: str,
    created_lai: int = 0,
    failed_lai: int = 0,
    failed_lai_ids: List[int] = [],
):
    assert f"Created action items: {created_lai}" in report
    assert f"Failed action items: {failed_lai}" in report
    assert f"Failed action item IDs: {failed_lai_ids}" in report


@pytest.mark.functional()
@pytest.mark.parametrize('frequency_mapping', [freq for freq in FrequencyMapping])
def test_generate_1_alert_per_each_period(_action_item, frequency_mapping):
    # expected
    expected = (
        "Created alerts items: 1. "
        "Failed alerts items [NO assignee]: 0. "
        "Failed alerts items: 0. "
        "Failed alerts item IDs: []."
    )

    # Generate dummy data
    _action_item.name = 'RAI-001'
    _action_item.metadata[MetadataFields.REFERENCE_ID.value] = 'RAI-001'
    _action_item.is_recurrent = bool(frequency_mapping.value.name)
    _action_item.is_required = True
    _action_item.recurrent_schedule = frequency_mapping.value.name
    _action_item.metadata[MetadataFields.IS_REVIEWED.value] = False
    _action_item.due_date = datetime.today() - relativedelta(days=1)

    _action_item.save()

    # exec process
    result = generate_alert_items()

    # validate
    assert expected == result


@pytest.mark.functional()
def test_generate_4_alert_when_schedule_weekly(_action_item):
    # expected
    expected = (
        "Created alerts items: 4. "
        "Failed alerts items [NO assignee]: 0. "
        "Failed alerts items: 0. "
        "Failed alerts item IDs: []."
    )

    expected_alerts = [
        ALERT_TYPES['CONTROL_PAST_DUE_ACTION_ITEM'],
        ALERT_TYPES['CONTROL_PAST_DUE_ACTION_ITEM'],
        ALERT_TYPES['CONTROL_PAST_DUE_ACTION_ITEM'],
        ALERT_TYPES['CONTROL_FUTURE_DUE_ACTION_ITEM'],
    ]

    # Generate data
    due_dates = [
        datetime.today() - relativedelta(weeks=1),
        datetime.today() - relativedelta(weeks=3),
        datetime.today(),
        datetime.today() + relativedelta(days=1),
        datetime.today() - relativedelta(days=1),
        datetime.today() + relativedelta(weeks=1),
    ]

    for index, due_date in enumerate(due_dates):
        new_action_item = copy_action_item(
            _action_item,
            index + 1,
            due_date,
            FrequencyMapping.WEEKLY.value.name,
            True,
            assignees=_action_item.assignees.all(),
        )
        create_policy_action_item(new_action_item, index + 2)
        create_action_item_without_type_field(new_action_item, index + 3)

    # exec process
    result = generate_alert_items()

    # validate
    assert (
        ActionItem.objects.filter(metadata__type=CONTROL_ACTION_ITEM_TYPE).count() == 6
    )
    assert Alert.objects.count() == 4

    created_alert = Alert.objects.all()
    for index, alerted in enumerate(expected_alerts):
        current_alert = created_alert[index]
        assert current_alert.sender == _action_item.assignees.first()
        assert current_alert.receiver == _action_item.assignees.first()
        assert current_alert.type == alerted

    assert expected == result


@pytest.mark.functional()
def test_generate_0_alert_when_schedule_weekly_and_no_assignee(_action_item):
    # expected
    expected = (
        "Created alerts items: 0. "
        "Failed alerts items [NO assignee]: 3. "
        "Failed alerts items: 0. "
        "Failed alerts item IDs: []."
    )

    # Generate data
    due_dates = [
        datetime.today() - relativedelta(weeks=1),
        datetime.today() - relativedelta(weeks=3),
        datetime.today() - relativedelta(days=1),
    ]

    for index, due_date in enumerate(due_dates):
        new_action_item = copy_action_item(
            _action_item, index + 1, due_date, FrequencyMapping.WEEKLY.value.name, True
        )
        create_policy_action_item(new_action_item, index + 2)
        create_action_item_without_type_field(new_action_item, index + 3)

    # exec process
    result = generate_alert_items()

    # validate
    assert (
        ActionItem.objects.filter(metadata__type=CONTROL_ACTION_ITEM_TYPE).count() == 3
    )
    assert Alert.objects.count() == 0
    assert expected == result


@pytest.mark.functional()
def test_generate_5_alert_when_schedule_bi_annually(_action_item):
    # expected
    expected = (
        "Created alerts items: 5. "
        "Failed alerts items [NO assignee]: 0. "
        "Failed alerts items: 0. "
        "Failed alerts item IDs: []."
    )

    expected_alerts = [
        ALERT_TYPES['CONTROL_PAST_DUE_ACTION_ITEM'],
        ALERT_TYPES['CONTROL_PAST_DUE_ACTION_ITEM'],
        ALERT_TYPES['CONTROL_FUTURE_DUE_ACTION_ITEM'],
        ALERT_TYPES['CONTROL_FUTURE_DUE_ACTION_ITEM'],
        ALERT_TYPES['CONTROL_FUTURE_DUE_ACTION_ITEM'],
    ]

    # Generate data
    due_dates = [
        datetime.today() + relativedelta(days=7),
        datetime.today() - relativedelta(weeks=1),
        datetime.today() - relativedelta(weeks=3),
        datetime.today() + relativedelta(months=1),
        datetime.today() + relativedelta(weeks=1),
    ]

    for index, due_date in enumerate(due_dates):
        new_action_item = copy_action_item(
            _action_item,
            index + 1,
            due_date,
            FrequencyMapping.BI_ANNUALLY.value.name,
            True,
            assignees=_action_item.assignees.all(),
        )
        create_policy_action_item(new_action_item, index + 2)
        create_action_item_without_type_field(new_action_item, index + 3)

    # exec process
    result = generate_alert_items()

    # validate
    assert (
        ActionItem.objects.filter(metadata__type=CONTROL_ACTION_ITEM_TYPE).count() == 5
    )
    assert Alert.objects.count() == 5

    created_alert = Alert.objects.all()
    for index, alerted in enumerate(expected_alerts):
        current_alert = created_alert[index]
        assert current_alert.sender == _action_item.assignees.first()
        assert current_alert.receiver == _action_item.assignees.first()
        assert current_alert.type == alerted

    assert expected == result


@pytest.mark.functional()
def test_generate_3_alert_when_schedule_immediately(_action_item):
    # expected
    expected = (
        "Created alerts items: 3. "
        "Failed alerts items [NO assignee]: 0. "
        "Failed alerts items: 0. "
        "Failed alerts item IDs: []."
    )

    expected_alerts = [
        ALERT_TYPES['CONTROL_PAST_DUE_ACTION_ITEM'],
        ALERT_TYPES['CONTROL_PAST_DUE_ACTION_ITEM'],
        ALERT_TYPES['CONTROL_FUTURE_DUE_ACTION_ITEM'],
    ]

    # Generate data
    due_dates = [
        datetime.today() + relativedelta(days=1),
        datetime.today() - relativedelta(weeks=10),
        datetime.today() - relativedelta(weeks=3),
        datetime.today() - relativedelta(days=1),
        datetime.today() - relativedelta(weeks=1),
        datetime.today() - relativedelta(years=1),
        datetime.today() + relativedelta(weeks=1),
    ]

    for index, due_date in enumerate(due_dates):
        new_action_item = copy_action_item(
            _action_item,
            index + 1,
            due_date,
            FrequencyMapping.IMMEDIATELY.value.name,
            False,
            assignees=_action_item.assignees.all(),
        )
        create_policy_action_item(new_action_item, index + 2)
        create_action_item_without_type_field(new_action_item, index + 3)

    # exec process
    result = generate_alert_items()

    # validate
    assert (
        ActionItem.objects.filter(metadata__type=CONTROL_ACTION_ITEM_TYPE).count() == 7
    )
    assert Alert.objects.count() == 3

    created_alert = Alert.objects.all()
    for index, alerted in enumerate(expected_alerts):
        current_alert = created_alert[index]
        assert current_alert.sender == _action_item.assignees.first()
        assert current_alert.receiver == _action_item.assignees.first()
        assert current_alert.type == alerted

    assert expected == result


@pytest.mark.functional()
def test_generate_0_alert_when_schedule_monthly(_action_item):
    # expected
    expected = (
        "Created alerts items: 0. "
        "Failed alerts items [NO assignee]: 0. "
        "Failed alerts items: 0. "
        "Failed alerts item IDs: []."
    )

    # Generate data
    due_dates = [
        datetime.today() + relativedelta(days=2),
        datetime.today() - relativedelta(days=2),
    ]

    for index, due_date in enumerate(due_dates):
        new_action_item = copy_action_item(
            _action_item,
            index + 1,
            due_date,
            FrequencyMapping.MONTHLY.value.name,
            True,
            assignees=_action_item.assignees.all(),
        )
        create_policy_action_item(new_action_item, index + 2)
        create_action_item_without_type_field(new_action_item, index + 3)

    # exec process
    result = generate_alert_items()

    # validate
    assert (
        ActionItem.objects.filter(metadata__type=CONTROL_ACTION_ITEM_TYPE).count() == 2
    )
    assert Alert.objects.count() == 0
    assert expected == result


@pytest.mark.functional()
def test_generate_0_alert_when_schedule_name_does_not_match(_action_item):
    # expected
    expected = (
        "Created alerts items: 0. "
        "Failed alerts items [NO assignee]: 0. "
        "Failed alerts items: 0. "
        "Failed alerts item IDs: []."
    )

    # Generate data
    due_dates = [
        datetime.today() + relativedelta(months=2),
        datetime.today() + relativedelta(years=1),
    ]

    for index, due_date in enumerate(due_dates):
        new_action_item = copy_action_item(
            _action_item,
            index + 1,
            due_date,
            FrequencyMapping.MONTHLY.value.name,
            True,
            assignees=_action_item.assignees.all(),
        )
        create_policy_action_item(new_action_item, index + 2)
        create_action_item_without_type_field(new_action_item, index + 3)

    # exec process
    result = generate_alert_items()

    # validate
    assert (
        ActionItem.objects.filter(metadata__type=CONTROL_ACTION_ITEM_TYPE).count() == 2
    )
    assert Alert.objects.count() == 0
    assert expected == result

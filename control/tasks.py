import logging
from copy import deepcopy
from datetime import date, datetime
from enum import Enum

from dateutil.relativedelta import relativedelta
from django.db.models import DateField, F, Q
from django.db.models.functions import ExtractWeekDay, Now, Trunc
from django.db.models.query import QuerySet

from action_item.models import ActionItem, ActionItemStatus
from alert.constants import ALERT_TYPES
from control.constants import CONTROL_TYPE, MetadataFields
from control.models import Control
from laika.celery import app as celery_app

logger = logging.getLogger(__name__)

RESTORATION_PERIOD_IN_WEEKS = 108
RESTORATION_PERIOD_IN_MONTHS = 26
CONTROL_ACTION_ITEM_TYPE = 'control'


# has_recurrent_past_due -> some past due actions are recurrent each 7 days
class Frequency:
    def __init__(
        self,
        name,
        duration,
        notice_period,
        past_due_notice_period,
        future_due_notice_period,
        has_recurrent_past_due,
    ):
        self.name = name
        self.duration = duration
        self.notice_period = notice_period
        self.has_recurrent_past_due = has_recurrent_past_due
        self.past_due_notice_period = past_due_notice_period
        self.future_due_notice_period = future_due_notice_period


class FrequencyMapping(Enum):
    IMMEDIATELY = Frequency(
        name='',
        duration=None,
        notice_period=None,
        has_recurrent_past_due=False,
        past_due_notice_period=[relativedelta(days=1), relativedelta(weeks=1)],
        future_due_notice_period=[relativedelta(days=1)],
    )
    WEEKLY = Frequency(
        name='weekly',
        duration=relativedelta(days=7),
        notice_period=relativedelta(days=7) - relativedelta(days=2),
        has_recurrent_past_due=True,
        past_due_notice_period=[relativedelta(days=1)],
        future_due_notice_period=[relativedelta(days=1), relativedelta(days=2)],
    )
    MONTHLY = Frequency(
        name='monthly',
        duration=relativedelta(months=1),
        notice_period=relativedelta(months=1) - relativedelta(weeks=1),
        has_recurrent_past_due=True,
        past_due_notice_period=[relativedelta(days=1)],
        future_due_notice_period=[relativedelta(days=1), relativedelta(weeks=1)],
    )
    QUARTERLY = Frequency(
        name='quarterly',
        duration=relativedelta(months=3),
        notice_period=relativedelta(months=3) - relativedelta(weeks=1),
        has_recurrent_past_due=True,
        past_due_notice_period=[relativedelta(days=1)],
        future_due_notice_period=[relativedelta(weeks=1), relativedelta(months=1)],
    )
    SEMI_ANNUALLY = Frequency(
        name='semi_annually',
        duration=relativedelta(months=6),
        notice_period=relativedelta(months=6) - relativedelta(months=1),
        has_recurrent_past_due=True,
        past_due_notice_period=[relativedelta(days=1)],
        future_due_notice_period=[
            relativedelta(days=1),
            relativedelta(weeks=1),
            relativedelta(months=1),
        ],
    )
    ANNUALLY = Frequency(
        name='annually',
        duration=relativedelta(years=1),
        notice_period=relativedelta(years=1) - relativedelta(months=1),
        has_recurrent_past_due=True,
        past_due_notice_period=[relativedelta(days=1)],
        future_due_notice_period=[
            relativedelta(days=1),
            relativedelta(weeks=1),
            relativedelta(months=1),
        ],
    )
    BI_ANNUALLY = Frequency(
        name='bi_annually',
        duration=relativedelta(years=2),
        notice_period=relativedelta(years=2) - relativedelta(months=1),
        has_recurrent_past_due=True,
        past_due_notice_period=[relativedelta(days=1)],
        future_due_notice_period=[
            relativedelta(days=1),
            relativedelta(weeks=1),
            relativedelta(months=1),
        ],
    )


@celery_app.task(name='Controls - generate recurrent action items and alerts')
def generate_recurrent_action_items_and_alerts():
    generated_action_items_payload = generate_recurrent_action_items()
    # TODO - Remove restore_not_created_recurrent_action_items method and
    # its related logic on December 2023
    restored_action_items_payload = restore_not_created_recurrent_action_items()
    generated_alert_items_payload = generate_alert_items()

    return (
        generated_action_items_payload
        + restored_action_items_payload
        + generated_alert_items_payload
    )


def _create_alerts_per_action_items(result_action_items, result_payload, alert_type):
    if not result_action_items.exists():
        return result_payload

    for action_item in result_action_items:
        try:
            if action_item.assignees.exists():
                owner = action_item.assignees.first()

                action_item.create_action_item_alert(
                    sender=owner,
                    receiver=owner,
                    alert_type=ALERT_TYPES[alert_type],
                    organization_id=owner.organization,
                )

                result_payload["created_alert_items"] += 1
            else:
                result_payload["failed_alert_items_without_assignee"] += 1
        except Exception as e:
            result_payload["failed_alert_items"] += 1
            result_payload["failed_alert_items_ids"].append(action_item.id)
            logger.exception(
                f'Failed to create new ALERT. {action_item.id=}. Error: {e}.'
            )


def generate_alert_items():
    result_payload = {
        "created_alert_items": 0,
        "failed_alert_items_without_assignee": 0,
        "failed_alert_items": 0,
        "failed_alert_items_ids": [],
    }

    logger.info("Execute generate alert item task.")
    for frequency_mapping in FrequencyMapping:
        past_action_items: list[
            ActionItem
        ] = _fetch_past_due_action_items_to_be_alerted(
            frequency_mapping.value,
        )

        future_action_items: list[
            ActionItem
        ] = _fetch_future_due_action_items_to_be_alerted(frequency_mapping.value)

        _create_alerts_per_action_items(
            past_action_items,
            result_payload,
            ALERT_TYPES['CONTROL_PAST_DUE_ACTION_ITEM'],
        )

        _create_alerts_per_action_items(
            future_action_items,
            result_payload,
            ALERT_TYPES['CONTROL_FUTURE_DUE_ACTION_ITEM'],
        )

    summary = (
        'Created alerts items: {created_alert_items}. '
        'Failed alerts items [NO assignee]: '
        '{failed_alert_items_without_assignee}. '
        'Failed alerts items: {failed_alert_items}. '
        'Failed alerts item IDs: {failed_alert_items_ids}.'.format(**result_payload)
    )

    logger.info(summary)
    return summary


def generate_annotate_recurrency(action_items):
    return action_items.annotate(
        week_day_due_date=ExtractWeekDay(F('due_date'))
    ).annotate(week_day_now=ExtractWeekDay(Now()))


def generate_filter_recurrency(frequency, filter_query):
    filter_query.add(
        Q(
            recurrent_schedule__iexact=frequency.name,
            week_day_due_date=F('week_day_now'),
            due_date__date__lt=datetime.now().date(),
        ),
        Q.OR,
    )

    return filter_query


def generate_filter_notice_period(frequency, filter_query):
    for action_item_frequency in frequency.past_due_notice_period:
        due_date = datetime.today() - action_item_frequency

        filter_query.add(
            Q(
                recurrent_schedule__iexact=frequency.name,
                due_date__year=due_date.year,
                due_date__month=due_date.month,
                due_date__day=due_date.day,
            ),
            Q.OR,
        )

    return filter_query


def _fetch_past_due_action_items_to_be_alerted(frequency):
    action_items = ActionItem.objects.filter(
        status=ActionItemStatus.NEW, metadata__type=CONTROL_ACTION_ITEM_TYPE
    )
    filter_query = Q()

    filter_query = generate_filter_notice_period(frequency, filter_query)

    if frequency.has_recurrent_past_due:
        action_items = generate_annotate_recurrency(action_items)
        filter_query = generate_filter_recurrency(frequency, filter_query)

    return action_items.filter(filter_query)


def _fetch_future_due_action_items_to_be_alerted(frequency):
    filter_query = Q()

    for action_item_frequency in frequency.future_due_notice_period:
        due_date = datetime.today() + action_item_frequency

        filter_query.add(
            Q(recurrent_schedule__iexact=frequency.name)
            & Q(due_date__year=due_date.year)
            & Q(due_date__month=due_date.month)
            & Q(due_date__day=due_date.day),
            Q.OR,
        )

    return ActionItem.objects.filter(
        filter_query, metadata__type=CONTROL_ACTION_ITEM_TYPE
    )


def generate_recurrent_action_items():
    created_action_items, failed_action_items = 0, 0
    failed_action_items_ids = []

    logger.info("Execute generate recurrent action item task.")
    for frequency_mapping in FrequencyMapping:
        action_items = _fetch_overdue_action_items(frequency=frequency_mapping.value)

        if not action_items.exists():
            continue

        for action_item in action_items:
            try:
                _create_recurrent_action_item(action_item, frequency_mapping.value)
                action_item.metadata[MetadataFields.IS_REVIEWED.value] = True
                action_item.save()
                created_action_items += 1
            except Exception as e:
                failed_action_items += 1
                failed_action_items_ids.append(action_item.id)
                logger.exception(
                    f'Failed to create recurring LAI. {action_item.id=}. Error: {e}.'
                )

    summary = (
        f"Created action items: {created_action_items}. "
        f"Failed action items: {failed_action_items}. "
        f"Failed action item IDs: {failed_action_items_ids}."
    )

    logger.info(summary)
    return summary


def _fetch_overdue_action_items(frequency: Frequency) -> QuerySet:
    due_date = datetime.today()

    if frequency.notice_period:
        due_date -= frequency.notice_period

    return ActionItem.objects.filter(
        Q(is_recurrent=True)
        & Q(recurrent_schedule__iexact=frequency.name)
        & Q(due_date__year=due_date.year)
        & Q(due_date__month=due_date.month)
        & Q(due_date__day=due_date.day)
        & Q(metadata__type=CONTROL_ACTION_ITEM_TYPE)
        & (
            ~Q(metadata__has_key=MetadataFields.IS_REVIEWED.value)
            | Q(metadata__isReviewed=False)
        )
    )


# TODO - Remove is_restoration_process variable and all its related logic
#  on December 2023
def _create_recurrent_action_item(
    action_item: ActionItem, frequency: Frequency, is_restoration_process=False
):
    new_action_item = deepcopy(action_item)
    new_action_item.id = None
    new_action_item.due_date = frequency.duration + (
        get_action_item_to_restore_due_date(frequency.notice_period)
        if is_restoration_process
        else action_item.due_date
    )
    new_action_item.status = ActionItemStatus.NEW
    new_action_item.is_required = False
    new_action_item.metadata[MetadataFields.TYPE.value] = CONTROL_TYPE
    new_action_item.metadata[MetadataFields.IS_REVIEWED.value] = False
    new_action_item.parent_action_item_id = (
        action_item.id
        if action_item.parent_action_item_id is None
        else action_item.parent_action_item_id
    )

    organization = action_item.controls.first().organization

    new_action_item.metadata[MetadataFields.REFERENCE_ID.value] = action_item.metadata[
        MetadataFields.REFERENCE_ID.value
    ]
    new_action_item.metadata[MetadataFields.ORGANIZATION_ID.value] = str(
        organization.id
    )

    new_action_item.full_clean()

    new_action_item.save()
    new_action_item.assignees.set(action_item.assignees.all())
    new_action_item.controls.set(action_item.controls.all())
    controls_to_update = []
    for control in new_action_item.controls.all():
        control.has_new_action_items = True
        controls_to_update.append(control)

    Control.objects.bulk_update(controls_to_update, ['has_new_action_items'])


def get_action_item_to_restore_due_date(notice_period):
    today = datetime.today()
    return today - notice_period


def weekly_not_created_action_items_dates(current_date):
    dates = []

    for week in range(0, RESTORATION_PERIOD_IN_WEEKS):
        new_date = current_date - relativedelta(weeks=week)
        dates.append(date(new_date.year, new_date.month, new_date.day))

    return dates


def monthly_not_created_action_items_dates(current_date):
    dates = []

    for month in range(0, RESTORATION_PERIOD_IN_MONTHS):
        new_date = current_date - relativedelta(months=month)
        dates.append(date(new_date.year, new_date.month, new_date.day))

    return dates


def quarterly_not_created_action_items_dates(current_date):
    dates = []

    for month in range(0, RESTORATION_PERIOD_IN_MONTHS, 3):
        new_date = current_date - relativedelta(months=month)
        dates.append(date(new_date.year, new_date.month, new_date.day))

    return dates


def semi_annually_not_created_action_items_dates(current_date):
    dates = []

    for month in range(0, RESTORATION_PERIOD_IN_MONTHS, 6):
        new_date = current_date - relativedelta(months=month)
        dates.append(date(new_date.year, new_date.month, new_date.day))

    return dates


def annually_not_created_action_items_dates(current_date):
    dates = []

    for month in range(0, RESTORATION_PERIOD_IN_MONTHS, 12):
        new_date = current_date - relativedelta(months=month)
        dates.append(date(new_date.year, new_date.month, new_date.day))

    return dates


def fetch_action_items_to_restore(frequency, action_items_due_dates_per_frequency):
    due_date = datetime.today()

    if frequency.notice_period:
        due_date -= frequency.notice_period

    due_dates_per_frequency = (
        action_items_due_dates_per_frequency[frequency.name](due_date)
        if action_items_due_dates_per_frequency.get(frequency.name)
        else []
    )

    action_items_with_truncated_due_date = ActionItem.objects.annotate(
        truncated_due_date=Trunc('due_date', 'day', output_field=DateField())
    )

    return action_items_with_truncated_due_date.filter(
        Q(is_recurrent=True)
        & Q(recurrent_schedule__iexact=frequency.name)
        & Q(metadata__type=CONTROL_ACTION_ITEM_TYPE)
        & (
            ~Q(metadata__has_key=MetadataFields.IS_REVIEWED.value)
            | Q(metadata__isReviewed=False)
        ),
        truncated_due_date__in=due_dates_per_frequency,
    )


def restore_not_created_recurrent_action_items():
    restored_action_items, failed_to_restore_action_items = 0, 0
    failed_to_restore_action_items_ids = []
    action_items_due_dates_per_frequency = {
        'weekly': weekly_not_created_action_items_dates,
        'monthly': monthly_not_created_action_items_dates,
        'quarterly': quarterly_not_created_action_items_dates,
        'semi_annually': semi_annually_not_created_action_items_dates,
        'annually': annually_not_created_action_items_dates,
    }

    logger.info('Start restoration for not created recurring action items.')

    for frequency in FrequencyMapping:
        logger.info(
            f'Fetching action items to restore for frequency: {frequency.value.name}.'
        )

        action_items = fetch_action_items_to_restore(
            frequency.value, action_items_due_dates_per_frequency
        )

        if not action_items.exists():
            continue

        for action_item in action_items:
            try:
                _create_recurrent_action_item(
                    action_item, frequency.value, is_restoration_process=True
                )
                action_item.metadata[MetadataFields.IS_REVIEWED.value] = True
                action_item.save()
                restored_action_items += 1
            except Exception as e:
                failed_to_restore_action_items += 1
                failed_to_restore_action_items_ids.append(action_item.id)
                logger.exception(
                    f'Failed to restore recurring action item: {action_item.id}. Error:'
                    f' {e}.'
                )

    summary = (
        f"Restored action items: {restored_action_items}. "
        f"Failed to restore action items: {failed_to_restore_action_items}. "
        f"Failed to restore action item IDs: {failed_to_restore_action_items_ids}."
    )

    logger.info(summary)

    return summary

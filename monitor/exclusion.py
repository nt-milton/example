from datetime import datetime
from typing import Iterable

from django.db.models import Max

from laika.utils.dates import YYYY_MM_DD_HH_MM_SS
from monitor.helpers import validate_user_monitor_exclusion_event
from monitor.models import (
    MonitorExclusion,
    MonitorExclusionEvent,
    MonitorExclusionEventType,
)
from monitor.result import Result
from monitor.sqlutils import add_criteria, not_in


def create_monitor_event(monitor_exclusion: MonitorExclusion, event_type: str):
    MonitorExclusionEvent.objects.create(
        monitor_exclusion=monitor_exclusion,
        justification=monitor_exclusion.justification,
        event_type=event_type,
    )


def renew_monitor_exclusion(monitor_exclusion: MonitorExclusion):
    create_monitor_event(monitor_exclusion, MonitorExclusionEventType.RENEWED)


def deprecate_monitor_exclusion(monitor_exclusion: MonitorExclusion):
    create_monitor_event(monitor_exclusion, MonitorExclusionEventType.DEPRECATED)


def validate_last_exclusion_event_type(
    monitor_exclusion_id: int, event_type: str
) -> bool:
    last_event = (
        MonitorExclusionEvent.objects.filter(
            monitor_exclusion__id=monitor_exclusion_id,
        )
        .order_by('-event_date')
        .first()
    )
    return last_event is not None and last_event.event_type == event_type


def find_exclude_idx(exclusion: MonitorExclusion, variables: list[dict]) -> int:
    not_found = -1
    if not variables:
        return not_found
    for idx, record_vars in enumerate(variables):
        row_value = str(record_vars.get(exclusion.key))
        if row_value == str(exclusion.value):
            return idx
    return not_found


def drop_by_index(array: list, indexes: list[int]):
    return [row for idx, row in enumerate(array) if idx not in indexes]


def exclude_result(
    result: Result, exclusion_criteria: Iterable[MonitorExclusion]
) -> Result:
    excluded_rows, drop_indexes = exclude_rows_by_exclusion_criteria(
        result, exclusion_criteria
    )

    return Result(
        columns=result.columns,
        data=drop_by_index(result.data, drop_indexes),
        excluded_results=excluded_rows,
        variables=drop_by_index(result.variables, drop_indexes),
    )


def exclude_rows_by_exclusion_criteria(
    result: Result, exclusion_criteria: Iterable[MonitorExclusion]
) -> tuple[dict, list[int]]:
    excluded_rows = dict(result.excluded_results)
    drop_indexes = []
    for exclusion in exclusion_criteria:
        found_idx = find_exclude_idx(exclusion, result.variables)
        if found_idx >= 0:
            excluded_rows[exclusion.id] = {
                'value': result.data[found_idx],
                'variables': result.variables[found_idx],
            }
            drop_indexes.append(found_idx)
    return excluded_rows, drop_indexes


def exclusion_events(result: Result, exclusion_criteria: Iterable[MonitorExclusion]):
    for exclusion in exclusion_criteria:
        if exclusion.id not in result.excluded_results:
            deprecate_monitor_exclusion(exclusion)
        elif validate_last_exclusion_event_type(
            exclusion.id, MonitorExclusionEventType.DEPRECATED
        ):
            renew_monitor_exclusion(exclusion)


def load_last_events(ids: list[int]) -> dict[int, datetime]:
    last_events = (
        MonitorExclusionEvent.objects.filter(monitor_exclusion__id__in=ids)
        .values_list('monitor_exclusion__id')
        .annotate(last_event=Max('event_date'))
    )
    return {exc_id: event_date for exc_id, event_date in last_events}


def load_exclusions(ids: list[int]) -> Iterable[MonitorExclusion]:
    return sort_exclusions(MonitorExclusion.objects.filter(id__in=ids))


def expand_result_with_exclusion(
    excluded_results: dict,
    exclusions: Iterable[MonitorExclusion],
    last_events: dict[int, datetime],
):
    for monitor_exclusion in exclusions:
        excluded_result = excluded_results.get(str(monitor_exclusion.id))
        if not excluded_result:
            continue
        value = (
            excluded_result
            if isinstance(excluded_result, list)
            else excluded_result.get('value', {})
        )
        last_event = last_events.get(monitor_exclusion.id)
        user = monitor_exclusion.last_event.user
        yield [
            validate_user_monitor_exclusion_event(user),
            monitor_exclusion.exclusion_date.strftime(YYYY_MM_DD_HH_MM_SS),
            last_event.strftime(YYYY_MM_DD_HH_MM_SS) if last_event else None,
            monitor_exclusion.justification,
            *value,
        ]


def sort_exclusions(exclusions: list[MonitorExclusion]) -> list[MonitorExclusion]:
    try:
        return sorted(exclusions, key=default_sort_int)
    except ValueError:
        return sorted(exclusions, key=default_sort)


def default_sort(exc: MonitorExclusion):
    return -int(exc.exclusion_date.timestamp()), exc.value


def default_sort_int(exc: MonitorExclusion):
    return -int(exc.exclusion_date.timestamp()), int(exc.value)


def add_exclusion_criteria(
    exclusions: list[MonitorExclusion], query: str, exclude_field: str
) -> str:
    values = [exclusion.value for exclusion in exclusions]
    return add_criteria(query, not_in(exclude_field, values))


def revert_exclusion(result: Result, exclusion_id: int) -> Result:
    if str(exclusion_id) not in result.excluded_results:
        return result
    excluded_results = result.excluded_results.copy()
    exclusion = excluded_results.pop(str(exclusion_id))
    data = result.data.copy()
    data.insert(0, exclusion['value'])
    variables = result.variables.copy()
    variables.insert(0, exclusion['variables'])
    return Result(
        columns=result.columns,
        data=data,
        excluded_results=excluded_results,
        variables=variables,
    )

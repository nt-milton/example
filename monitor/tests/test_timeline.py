from datetime import datetime, timedelta

import pytest

from monitor.models import MonitorInstanceStatus
from monitor.timeline import Interval, TimelineBuilder

NO_QUERY = ''
NO_CONDITION = ''
FIRST_EVENT_DATE = '2021-05-02 13:55:26'
LAST_EVENT_DATE = '2021-05-04 13:55:26'
HEALTHY = MonitorInstanceStatus.HEALTHY
NO_DATA_DETECTED = MonitorInstanceStatus.NO_DATA_DETECTED
TRIGGERED = MonitorInstanceStatus.TRIGGERED


def test_empty_results():
    end = datetime.today()
    start = end - timedelta(days=7)

    first, *_ = TimelineBuilder(start, end).build()

    assert first == (start, end, NO_DATA_DETECTED, NO_QUERY, NO_CONDITION)


def test_event_last_day():
    end = datetime.today()
    start = end - timedelta(days=7)
    event_date = end - timedelta(days=1)

    first, second, *_ = (
        TimelineBuilder(start, end)
        .append(event_date, HEALTHY, NO_QUERY, NO_CONDITION)
        .build()
    )

    assert first == (start, event_date, NO_DATA_DETECTED, NO_QUERY, NO_CONDITION)
    assert second == (event_date, end, HEALTHY, NO_QUERY, NO_CONDITION)


def test_event_last_two_days():
    end = datetime.today()
    start = end - timedelta(days=7)
    last_event = end - timedelta(days=1)
    second_last_event = end - timedelta(days=2)

    first, second, third, *_ = (
        TimelineBuilder(start, end)
        .append(second_last_event, TRIGGERED, NO_QUERY, NO_CONDITION)
        .append(last_event, HEALTHY, NO_QUERY, NO_CONDITION)
        .build()
    )

    assert first == (start, second_last_event, NO_DATA_DETECTED, NO_QUERY, NO_CONDITION)
    assert second == (second_last_event, last_event, TRIGGERED, NO_QUERY, NO_CONDITION)
    assert third == (last_event, end, HEALTHY, NO_QUERY, NO_CONDITION)


def test_event_merge():
    end = datetime.today()
    start = end - timedelta(days=7)
    last_event = end - timedelta(days=1)
    second_last_event = end - timedelta(days=2)

    first, second, *_ = (
        TimelineBuilder(start, end)
        .append(second_last_event, HEALTHY, NO_QUERY, NO_CONDITION)
        .append(last_event, HEALTHY, NO_QUERY, NO_CONDITION)
        .build()
    )

    assert first == (start, second_last_event, NO_DATA_DETECTED, NO_QUERY, NO_CONDITION)
    assert second == (second_last_event, end, HEALTHY, NO_QUERY, NO_CONDITION)


def test_out_range_before_interval():
    end = datetime.today()
    start = end - timedelta(days=7)
    out_range = end - timedelta(days=10)
    last_event_date = end - timedelta(days=1)

    first, second, *_ = (
        TimelineBuilder(start, end)
        .append(out_range, HEALTHY, NO_QUERY, NO_CONDITION)
        .append(last_event_date, TRIGGERED, NO_QUERY, NO_CONDITION)
        .build()
    )

    assert first == (start, last_event_date, HEALTHY, NO_QUERY, NO_CONDITION)
    assert second == (last_event_date, end, TRIGGERED, NO_QUERY, NO_CONDITION)


def test_out_range_after_interval():
    end = datetime.today()
    start = end - timedelta(days=7)
    out_range = end + timedelta(days=1)
    with pytest.raises(ValueError):
        TimelineBuilder(start, end).append(
            out_range, HEALTHY, NO_QUERY, NO_CONDITION
        ).build()


def test_complex():
    first_healthy = to_date(FIRST_EVENT_DATE)
    first_triggered = to_date(LAST_EVENT_DATE)
    third_healthy = to_date('2021-05-05 13:55:26')
    second_triggered = to_date('2021-05-07 13:55:26')
    events = [
        (first_healthy, HEALTHY),
        (to_date('2021-05-03 13:55:26'), HEALTHY),
        (first_triggered, TRIGGERED),
        (third_healthy, HEALTHY),
        (second_triggered, TRIGGERED),
    ]
    end = to_date('2021-05-09 13:55:26')
    start = end - timedelta(days=8)
    builder = TimelineBuilder(start, end)
    for event_date, status in events:
        builder.append(event_date, status, NO_QUERY, NO_CONDITION)
    timeline = builder.build()

    expected_intervals = [
        Interval(start, first_healthy, NO_DATA_DETECTED, NO_QUERY, NO_CONDITION),
        Interval(first_healthy, first_triggered, HEALTHY, NO_QUERY, NO_CONDITION),
        Interval(first_triggered, third_healthy, TRIGGERED, NO_QUERY, NO_CONDITION),
        Interval(third_healthy, second_triggered, HEALTHY, NO_QUERY, NO_CONDITION),
        Interval(second_triggered, end, TRIGGERED, NO_QUERY, NO_CONDITION),
    ]

    assert timeline == expected_intervals


def test_duplicate_event():
    events = [
        (to_date(FIRST_EVENT_DATE), HEALTHY, NO_QUERY),
        (to_date(LAST_EVENT_DATE), TRIGGERED, NO_QUERY),
        (to_date(LAST_EVENT_DATE), TRIGGERED, NO_QUERY),
    ]
    end = to_date('2021-05-09 13:55:26')
    start = end - timedelta(days=8)
    builder = TimelineBuilder(start, end)
    for event_date, status, query in events:
        builder.append(event_date, status, query, NO_CONDITION)
    timeline = builder.build()

    expected_status = ['no_data_detected', 'healthy', 'triggered']
    assert [line.status for line in timeline] == expected_status


def test_query_change():
    events = [
        (to_date(FIRST_EVENT_DATE), HEALTHY, NO_QUERY),
        (to_date(LAST_EVENT_DATE), TRIGGERED, NO_QUERY),
        (to_date(LAST_EVENT_DATE), TRIGGERED, 'select * from lo_users'),
    ]
    end = to_date('2021-05-09 12:55:26')
    start = end - timedelta(days=8)
    builder = TimelineBuilder(start, end)
    for event_date, status, query in events:
        builder.append(event_date, status, query, NO_CONDITION)
    timeline = builder.build()

    expected_status = ['no_data_detected', 'healthy', 'triggered', 'triggered']
    assert [line.status for line in timeline] == expected_status

    expected_queries = [NO_QUERY, NO_QUERY, NO_QUERY, 'select * from lo_users']
    assert [line.query for line in timeline] == expected_queries


def to_date(text):
    return datetime.strptime(text, '%Y-%m-%d %H:%M:%S')

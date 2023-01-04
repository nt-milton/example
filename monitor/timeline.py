from collections import namedtuple

from monitor.models import MonitorInstanceStatus

NO_DATA_DETECTED = MonitorInstanceStatus.NO_DATA_DETECTED

Interval = namedtuple(
    'Interval', ['start', 'end', 'status', 'query', 'health_condition']
)


class TimelineBuilder:
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.intervals = [Interval(self.start, self.end, NO_DATA_DETECTED, '', '')]

    def append(self, event_date, status, query, health_condition):
        idx, interval = self._find_interval(event_date)
        if not interval:
            if event_date > self.end:
                raise ValueError('Out of range')
            first, *_ = self.intervals
            self.intervals[0] = Interval(
                first.start, first.end, status, query, health_condition
            )

            return self
        if interval.status == status and interval.query == query:
            return self
        self.intervals[idx] = Interval(
            interval.start,
            event_date,
            interval.status,
            interval.query,
            interval.health_condition,
        )
        self.intervals.insert(
            idx + 1, Interval(event_date, interval.end, status, query, health_condition)
        )

        return self

    def build(self):
        return self.intervals

    def _find_interval(self, event_date):
        for idx, interval in enumerate(self.intervals):
            if interval.start <= event_date < interval.end:
                return idx, interval

        return None, None

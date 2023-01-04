from collections import defaultdict
from datetime import timedelta
from typing import Iterable

from django.db.models import Max, Q
from django.utils import timezone
from promise import Promise
from promise.dataloader import DataLoader

from laika.data_loaders import ContextDataLoader, LoaderById
from program.constants import SUBTASK_MONITOR_STATUS_EMPTY as MONITOR_EMPTY
from program.constants import SUBTASK_MONITOR_STATUS_NO_RELATED as NO_RELATED
from program.constants import SUBTASK_MONITOR_STATUS_RELATED as MONITOR_RELATED
from user.admin import User

from .models import (
    Monitor,
    MonitorResult,
    MonitorUserEvent,
    MonitorUserEventsOptions,
    OrganizationMonitor,
)

RECENT_USER_DAYS = 15
RECENT_MONITOR_DAYS = 30


class MonitorLoaders:
    def __init__(self, context):
        self.last_monitor_result = MonitorResultLoader()
        self.monitor_subtask = MonitorSubtaskLoader.with_context(context)
        self.monitor_by_id = LoaderById(Monitor)
        self.new_badge = NewBadgeLoader.with_context(context)


class MonitorResultLoader(DataLoader):
    @staticmethod
    def batch_load_fn(keys: list) -> Promise:
        max_monitor_results = dict(
            MonitorResult.objects.filter(organization_monitor_id__in=keys)
            .values_list('organization_monitor_id')
            .annotate(Max('id'))
        )
        latest_results = MonitorResult.objects.filter(
            id__in=max_monitor_results.values()
        )
        results_by_monitor = {
            result.organization_monitor_id: result for result in latest_results
        }

        return Promise.resolve(
            [results_by_monitor.get(monitor_id) for monitor_id in keys]
        )


class MonitorSubtaskLoader(ContextDataLoader):
    def batch_load_fn(self, keys: list) -> Promise:
        criteria = Q()
        for key in keys:
            criteria |= Q(subtask_reference__contains=str(key))

        matching_monitors = list(Monitor.objects.filter(criteria))

        matching_org_monitors = group_by_subtask_reference(
            OrganizationMonitor.objects.filter(
                organization=self.context.user.organization,
                active=True,
                monitor__in={m.id for m in matching_monitors},
            ).select_related('monitor')
        )
        matching_monitor_ref = (
            ref for m in matching_monitors for ref in m.subtask_reference.split()
        )
        status = monitor_status(matching_monitor_ref, matching_org_monitors.keys())
        return Promise.resolve(
            [(status[str(ref)], matching_org_monitors[str(ref)]) for ref in keys]
        )


def group_by_subtask_reference(or_monitors: Iterable[OrganizationMonitor]) -> dict:
    result = defaultdict(set)
    for om in or_monitors:
        keys = om.monitor.subtask_reference.split()
        for ref in keys:
            result[ref].add(om)
    return result


def monitor_status(
    matching_monitor_ref: Iterable[str], org_matching_monitor_ref: Iterable[str]
) -> dict:
    result = defaultdict(lambda: MONITOR_EMPTY)
    for key in matching_monitor_ref:
        result[key] = NO_RELATED
    for key in org_matching_monitor_ref:
        result[key] = MONITOR_RELATED
    return result


class NewBadgeLoader(ContextDataLoader):
    def batch_load_fn(self, keys: list) -> Promise:
        user = self.context.user
        new_org_monitor_ids = get_new_org_monitors(user)
        return Promise.resolve(
            [(org_monitor.id in new_org_monitor_ids) for org_monitor in keys]
        )


def get_new_org_monitors(user: User) -> list[int]:
    events = dashboard_views(user)
    visited_monitors = viewed_monitors(user)
    org_monitors = OrganizationMonitor.objects.filter(organization=user.organization)
    return [
        monitor.id
        for monitor in org_monitors
        if verify_is_new(monitor, user, events, visited_monitors)
    ]


def verify_is_new(
    org_monitor: OrganizationMonitor,
    user: User,
    dashboard_events: list[MonitorUserEvent],
    visited_monitors: list[OrganizationMonitor],
) -> bool:
    recent_join = (timezone.now() - user.date_joined).days < RECENT_USER_DAYS
    if recent_join:
        return False
    if user.date_joined > org_monitor.created_at:
        return False
    return (
        not more_one_month_older(org_monitor)
        and org_monitor not in visited_monitors
        and not pass_week_after_view_dashboard(org_monitor, dashboard_events)
    )


def more_one_month_older(organization_monitor: OrganizationMonitor) -> bool:
    days = (timezone.now() - organization_monitor.created_at).days
    return days > RECENT_MONITOR_DAYS


def viewed_monitors(user: User) -> list[OrganizationMonitor]:
    return list(
        OrganizationMonitor.objects.filter(
            monitoruserevent__event=MonitorUserEventsOptions.VIEW_DETAIL,
            monitoruserevent__user=user,
        ).distinct()
    )


def dashboard_views(user: User) -> list[MonitorUserEvent]:
    return list(
        MonitorUserEvent.objects.filter(
            user=user,
            event_time__gte=timezone.now() - timedelta(days=RECENT_MONITOR_DAYS),
            event=MonitorUserEventsOptions.VIEW_DASHBOARD,
        ).order_by('event_time')
    )


def pass_week_after_view_dashboard(
    organization_monitor: OrganizationMonitor, dashboard_events: list[MonitorUserEvent]
) -> bool:
    created_at = organization_monitor.created_at
    event = next((evt for evt in dashboard_events if evt.event_time > created_at), None)
    if not event:
        return False
    return timezone.now() > (event.event_time + timedelta(days=7))

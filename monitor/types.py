import logging
from datetime import datetime, timedelta

import graphene
from graphene_django import DjangoObjectType

from control.types import ControlType
from laika.types import BaseResponseType, PaginationResponseType
from monitor import template
from monitor.constants import (
    INTEGRATION_DESCRIPTION,
    LAIKA_APP_DESCRIPTION,
    LAIKA_OBJECT_DESCRIPTION,
    SOURCE_SYSTEM_CHOICES,
)
from monitor.exclusion import add_exclusion_criteria
from monitor.models import (
    Monitor,
    MonitorExclusion,
    MonitorInstanceStatus,
    MonitorResult,
    MonitorSubscriptionEvent,
    MonitorSubscriptionEventType,
)
from monitor.models import MonitorType as MonitorTypeChoice
from monitor.models import (
    MonitorUserEvent,
    MonitorUserEventsOptions,
    OrganizationMonitor,
)
from monitor.timeline import TimelineBuilder
from tag.types import TagType
from user.models import User
from user.types import UserType
from user.watcher_list.types import WatcherListType

LAIKA_APP = 'Laika App'
CUSTOM = 'Custom'

logger = logging.getLogger(__name__)


class MonitorType(DjangoObjectType):
    class Meta:
        model = Monitor
        fields = (
            'id',
            'name',
            'urgency',
            'query',
            'description',
            'monitor_type',
            'status',
            'health_condition',
            'frequency',
            'runner_type',
            'parent_monitor',
            'control_references',
            'take_action',
            'exclude_field',
            'source_systems',
        )

    id = graphene.ID()
    name = graphene.String()
    urgency = graphene.String()
    query = graphene.String()
    description = graphene.String()
    monitor_type = graphene.String()
    status = graphene.String()
    health_condition = graphene.String()
    frequency = graphene.String()
    runner_type = graphene.String()
    parent_monitor = graphene.ID()
    control_references = graphene.String()
    take_action = graphene.String()
    exclude_field = graphene.String()
    source_systems = graphene.JSONString()

    def resolve_source_systems(self, info):
        source_systems = []
        if (
            self.monitor_type == MonitorTypeChoice.CUSTOM
            and CUSTOM not in source_systems
        ):
            source_systems.append(CUSTOM)
        if not self.source_systems:
            return source_systems
        try:
            for source_system in self.source_systems:
                source_system_found = [
                    system_choice
                    for system_choice in SOURCE_SYSTEM_CHOICES
                    if system_choice[0] == source_system
                ][0][1]
                if INTEGRATION_DESCRIPTION in source_system_found:
                    source_systems.append(
                        source_system_found.replace(
                            f' {INTEGRATION_DESCRIPTION}', ''
                        ).replace('_', ' ')
                    )
                elif (
                    LAIKA_APP_DESCRIPTION in source_system_found
                    or LAIKA_OBJECT_DESCRIPTION in source_system_found
                ) and LAIKA_APP not in source_systems:
                    source_systems.append(LAIKA_APP)

            return source_systems
        except Exception as e:
            logger.error(f'Error resolving source systems: {e}')
        return []

    def resolve_id(self, info):
        return self.id


class MonitorResultType(DjangoObjectType):
    class Meta:
        model = MonitorResult
        fields = ('id', 'created_at', 'result', 'status')

    id = graphene.ID()
    created_at = graphene.DateTime()
    result = graphene.JSONString()
    status = graphene.String()
    fix_me_links = graphene.List(graphene.String)
    can_exclude = graphene.Boolean()

    def resolve_fix_me_links(self, info) -> list[str]:
        return template.build_fix_links(self.organization_monitor, self.result)

    def resolve_can_exclude(self: MonitorResult, info) -> bool:
        return self.can_exclude()


class QueryExecution(graphene.ObjectType):
    result = graphene.JSONString()
    fix_me_links = graphene.List(graphene.String)


class OrganizationMonitorIntervalType(graphene.ObjectType):
    id = graphene.Int()
    start = graphene.DateTime()
    end = graphene.DateTime()
    status = graphene.String()
    query = graphene.String()
    health_condition = graphene.String()


def get_timeline(monitor_results, timelapse):
    end = datetime.today()
    start = end - timedelta(timelapse)
    timeline = TimelineBuilder(start, end)
    for monitor_result in monitor_results:
        event_datetime = monitor_result.created_at.replace(tzinfo=None)
        timeline.append(
            event_datetime,
            monitor_result.status,
            monitor_result.query,
            monitor_result.health_condition,
        )
    return timeline


def build_timeline_by_timelapse(monitor_results, timelapse):
    timeline = get_timeline(monitor_results, timelapse)
    result = []
    for index, interval in enumerate(timeline.build()):
        result.append(
            OrganizationMonitorIntervalType(
                index,
                interval.start,
                interval.end,
                interval.status,
                interval.query,
                interval.health_condition,
            )
        )
    return result


class OrganizationMonitorType(DjangoObjectType):
    class Meta:
        model = OrganizationMonitor
        fields = (
            'id',
            'organization',
            'monitor',
            'active',
            'controls',
            'tags',
            'status',
        )

    id = graphene.ID()
    display_id = graphene.String()
    monitor = graphene.Field(MonitorType)
    organization_id = graphene.String()
    last_result = graphene.Field(MonitorResultType)
    last_run = graphene.DateTime()
    active = graphene.Boolean()
    status = graphene.String()
    controls = graphene.List(ControlType)
    tags = graphene.List(TagType)
    timeline = graphene.List(OrganizationMonitorIntervalType)
    watcher_list = graphene.Field(WatcherListType)
    exclude_field = graphene.String()
    exclusion_query = graphene.String()
    show_fix_me_link = graphene.Boolean()
    viewed = graphene.Boolean()
    toggled_by_system = graphene.Boolean()
    is_user_watching = graphene.Boolean()
    urgency = graphene.String()

    def resolve_display_id(self, info):
        return self.monitor.display_id

    def resolve_is_user_watching(self, info):
        current_user = info.context.user
        return self.watcher_list.users.filter(id=current_user.id).exists()

    def resolve_show_fix_me_link(self, info):
        return self.monitor.fix_me_link and not self.monitor.is_custom()

    def resolve_exclusion_query(self, info):
        exclusions = MonitorExclusion.objects.filter(
            organization_monitor__id=self.id,
            is_active=True,
        )

        return add_exclusion_criteria(
            exclusions, self.monitor.query, self.monitor.exclude_field
        )

    def resolve_exclude_field(self, info):
        return self.monitor.exclude_field

    def resolve_organization_id(self, info):
        return self.organization_id

    @staticmethod
    def resolve_monitor(root, info):
        monitor_loader = info.context.loaders.monitor

        def merge(monitor):
            if root.name:
                monitor.name = root.name
            if root.description:
                monitor.description = root.description
            if root.query:
                monitor.query = root.query
            return monitor

        return monitor_loader.monitor_by_id.load(root.monitor_id).then(merge)

    @staticmethod
    def resolve_last_result(root, info):
        return last_result(info, root.id)

    @staticmethod
    def resolve_last_run(root, info):
        result = last_result(info, root.id)
        return result.then(lambda mr: mr.created_at if mr else None)

    def resolve_timeline(self, info):
        timelapse = info.variable_values.get('timelapse', 7)
        monitor_results = MonitorResult.objects.filter(
            organization_monitor=self
        ).order_by('id')
        return build_timeline_by_timelapse(monitor_results, timelapse)

    def resolve_controls(self, info):
        return self.controls.all().order_by('display_id')

    def resolve_tags(self, info):
        return self.tags.order_by('name')

    def resolve_watcher_list(self, info):
        return self.watcher_list

    def resolve_viewed(self, info):
        monitor_loader = info.context.loaders.monitor
        return monitor_loader.new_badge.load(self)

    def resolve_urgency(self, info):
        if self.urgency:
            return self.urgency

        monitor_loader = info.context.loaders.monitor

        def get_urgency(monitor: Monitor):
            return monitor.urgency

        return monitor_loader.monitor_by_id.load(self.monitor_id).then(get_urgency)


class MonitorStatsType(graphene.ObjectType):
    actives = graphene.Int()
    inactives = graphene.Int()
    actives_flagged = graphene.Int()
    is_user_subscribed = graphene.Boolean()
    can_user_subscribe = graphene.Boolean()


class ControlStatsType(graphene.ObjectType):
    actives = graphene.Int()
    inactives = graphene.Int()


class ControlMonitorsResponseType(BaseResponseType):
    results = graphene.List(OrganizationMonitorType)
    control_stats = graphene.Field(ControlStatsType)
    pagination = graphene.Field(PaginationResponseType)


SUPER_ADMIN_ROLE = 'SuperAdmin'
ADMIN_ROLE = 'OrganizationAdmin'
CONTRIBUTOR_ROLE = 'OrganizationMember'
SUBSCRIPTION_ROLES = [SUPER_ADMIN_ROLE, ADMIN_ROLE, CONTRIBUTOR_ROLE]


def validate_user_subscribed(organization_id: str, current_user: User) -> bool:
    monitor_subscription = MonitorSubscriptionEvent.objects.filter(
        organization_id=organization_id, user=current_user
    ).first()
    is_user_admin = current_user.role == ADMIN_ROLE
    is_event_subscribed = (
        monitor_subscription
        and monitor_subscription.event_type == MonitorSubscriptionEventType.SUBSCRIBED
    )
    is_admin_subscribed = (
        is_user_admin and not monitor_subscription or is_event_subscribed
    )
    is_non_default_subscribed = not is_user_admin and is_event_subscribed
    return bool(is_admin_subscribed or is_non_default_subscribed)


class MonitorUserEventType(graphene.ObjectType):
    show_banner = graphene.Boolean()


class OrganizationMonitorsResponseType(BaseResponseType):
    all_ids = graphene.List(graphene.String)
    results = graphene.List(OrganizationMonitorType)
    stats = graphene.Field(MonitorStatsType)
    pagination = graphene.Field(PaginationResponseType)
    events = graphene.Field(MonitorUserEventType)

    @staticmethod
    def resolve_stats(root, info):
        current_user = info.context.user
        organization_id = current_user.organization_id
        actives = OrganizationMonitor.objects.filter(
            organization_id=organization_id, active=True
        ).count()
        inactives = OrganizationMonitor.objects.filter(
            organization_id=organization_id, active=False
        ).count()
        actives_flagged = OrganizationMonitor.objects.filter(
            organization_id=organization_id,
            active=True,
            status=MonitorInstanceStatus.TRIGGERED,
        ).count()
        is_user_subscribed = validate_user_subscribed(organization_id, current_user)
        can_user_subscribe = current_user.role in SUBSCRIPTION_ROLES
        return MonitorStatsType(
            actives=actives,
            inactives=inactives,
            actives_flagged=actives_flagged,
            is_user_subscribed=is_user_subscribed,
            can_user_subscribe=can_user_subscribe,
        )

    @staticmethod
    def resolve_events(root, info):
        from monitor.filters import (
            filter_by_organization,
            get_query_for_non_laika_monitors,
        )

        monitor_close_banner_events = MonitorUserEvent.objects.filter(
            user=info.context.user, event=MonitorUserEventsOptions.CLOSE_DYNAMIC_BANNER
        ).count()
        total_org_non_laika_monitors = OrganizationMonitor.objects.filter(
            filter_by_organization(info.context.user.organization_id)
            & get_query_for_non_laika_monitors()
        ).count()
        show_banner = (
            monitor_close_banner_events == 0 and total_org_non_laika_monitors == 0
        )
        return MonitorUserEventType(show_banner=show_banner)


class MonitorExclusionType(DjangoObjectType):
    class Meta:
        model = MonitorExclusion
        fields = (
            'id',
            'value',
            'exclusion_date',
            'is_active',
            'snapshot',
            'justification',
        )

    column = graphene.String()

    def resolve_column(self, info):
        return self.key


class ExcludedResultType(graphene.ObjectType):
    columns = graphene.List(graphene.String)
    data = graphene.List(graphene.List(graphene.String))
    fix_me_links = graphene.List(graphene.String)
    exclusion_ids = graphene.List(graphene.String)


class MonitorExclusionResultType(graphene.ObjectType):
    monitor_exclusions = graphene.List(MonitorExclusionType)


class MonitorsWatchersType(graphene.ObjectType):
    watchers = graphene.List(UserType)


def last_result(info, id):
    monitor_loader = info.context.loaders.monitor
    return monitor_loader.last_monitor_result.load(id)


def convert_to_dict(row: list[str], columns: list[str]) -> dict[str, str]:
    return {column_name.lower(): value for column_name, value in zip(columns, row)}

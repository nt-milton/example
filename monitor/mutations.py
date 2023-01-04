import logging

import graphene

from laika.decorators import laika_service
from laika.utils.exceptions import ServiceException
from organization.models import Organization
from user.models import User, WatcherList
from user.signals import (
    assign_user_to_watcher_lists_in_organization,
    remove_user_from_watcher_lists_in_organization,
)
from user.types import UserType

from .action_item import reconcile_action_items
from .constants import WATCH
from .exclusion import exclude_result, revert_exclusion
from .inputs import BulkWatchInput, MonitorExclusionInputType
from .models import (
    Monitor,
    MonitorExclusion,
    MonitorExclusionEvent,
    MonitorExclusionEventType,
    MonitorFrequency,
    MonitorResult,
    MonitorStatus,
    MonitorSubscriptionEvent,
    MonitorSubscriptionEventType,
    MonitorType,
    MonitorUserEvent,
    OrganizationMonitor,
    infer_context_from_query,
)
from .result import Result
from .runner import NO_DATASOURCE_RESULT, asyn_run, save_result
from .sqlutils import compatible_queries
from .types import MonitorExclusionType, OrganizationMonitorType

logger = logging.getLogger(__name__)


class AddUserMonitorEvent(graphene.Mutation):
    user = graphene.Field(UserType)
    event = graphene.String()
    event_time = graphene.DateTime()
    organization_monitor = graphene.Field(OrganizationMonitorType)

    class Arguments:
        organization_monitor_id = graphene.ID()
        event = graphene.String(required=True)

    @laika_service(
        permission='monitor.change_monitor',
        exception_msg='Failed to create monitor user event',
    )
    def mutate(self, info, **kwargs):
        organization_monitor_id = kwargs.get('organization_monitor_id')
        event = kwargs.get('event')
        organization_monitor = OrganizationMonitor.objects.filter(
            id=organization_monitor_id, organization=info.context.user.organization
        ).first()
        instance = MonitorUserEvent.objects.create(
            user=info.context.user,
            event=event,
            organization_monitor=organization_monitor,
        )
        return AddUserMonitorEvent(
            user=instance.user,
            event=instance.event,
            event_time=instance.event_time,
            organization_monitor=instance.organization_monitor,
        )


class CreateMonitorExclusion(graphene.Mutation):
    monitor_exclusions = graphene.List(MonitorExclusionType)

    class Arguments:
        organization_monitor_id = graphene.ID(required=True)
        monitor_exclusion = MonitorExclusionInputType(required=True)

    @laika_service(
        permission='monitor.change_monitor',
        exception_msg='Failed to create monitor exclusion criteria',
    )
    def mutate(self, info, **kwargs):
        organization_monitor_id = kwargs.get('organization_monitor_id')
        monitor_exclusion = kwargs.get('monitor_exclusion')
        data_indexes = monitor_exclusion.data_indexes
        justification = monitor_exclusion.justification
        organization_monitor = OrganizationMonitor.objects.get(
            id=organization_monitor_id, organization=info.context.user.organization
        )
        key = organization_monitor.monitor.exclude_field
        exclusions = []
        last_result = (
            MonitorResult.objects.filter(organization_monitor=organization_monitor)
            .order_by('-created_at')
            .first()
        )
        monitor_result = last_result.result
        for data_index in data_indexes:
            snapshot = monitor_result['data'][data_index]
            value = monitor_result['variables'][data_index][key]
            if MonitorExclusion.objects.filter(
                organization_monitor=organization_monitor,
                key=key,
                value=value,
                is_active=True,
            ).exists():
                raise ServiceException(
                    f'Exclusion in {organization_monitor.monitor.name} '
                    f'for {key}: {value} in company '
                    f'{organization_monitor.organization.name} already exists.'
                )
            instance = MonitorExclusion.objects.create(
                organization_monitor=organization_monitor,
                key=key,
                value=value,
                snapshot=snapshot,
                justification=justification,
            )
            store_create_event(instance, info.context.user)
            exclusions.append(instance)
        updated = exclude_result(Result(**monitor_result), exclusions)
        update_status(updated, last_result)
        return CreateMonitorExclusion(monitor_exclusions=exclusions)


class UpdateMonitorExclusion(graphene.Mutation):
    monitor_exclusions = graphene.List(MonitorExclusionType)

    class Arguments:
        organization_monitor_id = graphene.ID(required=True)
        monitor_exclusion_ids = graphene.List(graphene.String)
        justification = graphene.String(required=True)

    @laika_service(
        permission='monitor.change_monitor',
        exception_msg='Failed to update monitor exclusion criteria',
    )
    def mutate(self, info, **kwargs):
        organization_monitor_id = kwargs.get('organization_monitor_id')
        monitor_exclusion_ids = kwargs.get('monitor_exclusion_ids')
        justification = kwargs.get('justification')
        user = info.context.user
        monitor_exclusions = []
        OrganizationMonitor.objects.get(
            id=organization_monitor_id, organization=info.context.user.organization
        )
        for exclusion_id in monitor_exclusion_ids:
            instance = MonitorExclusion.objects.get(
                id=exclusion_id,
                organization_monitor=organization_monitor_id,
            )
            instance.justification = justification
            instance.save()
            monitor_exclusions.append(instance)
            MonitorExclusionEvent.objects.create(
                monitor_exclusion=instance,
                justification=justification,
                event_type=(MonitorExclusionEventType.UPDATED_JUSTIFICATION),
                user=user,
            )
        return UpdateMonitorExclusion(monitor_exclusions=monitor_exclusions)


class RevertMonitorExclusion(graphene.Mutation):
    monitor_exclusions = graphene.List(MonitorExclusionType)

    class Arguments:
        organization_monitor_id = graphene.ID(required=True)
        monitor_exclusion_ids = graphene.List(graphene.String)

    @laika_service(
        permission='monitor.change_monitor',
        exception_msg='Failed to delete monitor exclusion criteria',
    )
    def mutate(self, info, **kwargs):
        user = info.context.user
        organization_monitor_id = kwargs.get('organization_monitor_id')
        organization_monitor = OrganizationMonitor.objects.get(
            id=organization_monitor_id, organization=info.context.user.organization
        )
        monitor_exclusion_ids = kwargs.get('monitor_exclusion_ids')
        instances = MonitorExclusion.objects.filter(
            id__in=monitor_exclusion_ids,
            organization_monitor=organization_monitor_id,
        )

        for instance in instances:
            instance.is_active = False
            instance.save()
            MonitorExclusionEvent.objects.create(
                monitor_exclusion=instance,
                justification=instance.justification,
                event_type=MonitorExclusionEventType.DELETED,
                user=user,
            )

        last_result = (
            MonitorResult.objects.filter(organization_monitor=organization_monitor)
            .order_by('-created_at')
            .first()
        )
        updated = Result(**last_result.result)
        for exc_id in monitor_exclusion_ids:
            updated = revert_exclusion(updated, int(exc_id))
        update_status(updated, last_result)
        return RevertMonitorExclusion(monitor_exclusions=instances)


class UpdateOrganizationMonitor(graphene.Mutation):
    organization_monitor = graphene.Field(OrganizationMonitorType)

    class Arguments:
        id = graphene.String()
        active = graphene.Boolean()

    @laika_service(
        permission='monitor.change_monitor', exception_msg='Failed to update monitors'
    )
    def mutate(self, info, id, active):
        organization_monitor = OrganizationMonitor.objects.get(
            monitor_id=id, organization=info.context.user.organization
        )
        organization_monitor.active = active
        organization_monitor.toggled_by_system = False
        organization_monitor.save()
        if not active:
            save_result(organization_monitor, NO_DATASOURCE_RESULT)
        else:
            reconcile_action_items(organization_monitor)
        return UpdateOrganizationMonitor(organization_monitor=organization_monitor)


class AddCustomMonitorWithoutParent(graphene.Mutation):
    organization_monitor = graphene.Field(OrganizationMonitorType)

    class Arguments:
        description = graphene.String()
        name = graphene.String()
        health_condition = graphene.String()
        urgency = graphene.String()
        query = graphene.String()

    @laika_service(
        atomic=False,
        permission='monitor.change_monitor',
        exception_msg='Failed to create monitor',
    )
    def mutate(self, info, **kwargs):
        organization = info.context.user.organization
        query = kwargs.get('query')
        runner_type = infer_context_from_query(query)
        monitor = Monitor.objects.create(
            **kwargs,
            runner_type=runner_type,
            organization=organization,
            monitor_type=MonitorType.CUSTOM,
            status=MonitorStatus.ACTIVE,
            frequency=MonitorFrequency.DAILY,
        )
        organization_monitor = OrganizationMonitor.objects.create(
            organization=organization, monitor=monitor, active=True
        )
        asyn_run(organization_monitor)
        return AddCustomMonitorWithoutParent(organization_monitor=organization_monitor)


class ExecuteOrganizationMonitor(graphene.Mutation):
    organization_monitor = graphene.Field(OrganizationMonitorType)

    class Arguments:
        id = graphene.String()

    @laika_service(
        atomic=False,
        permission='monitor.change_monitor',
        exception_msg='Failed to execute monitor',
    )
    def mutate(self, info, id):
        user = info.context.user
        logger.info(f'Execute org monitor: {id}')
        organization_monitor = OrganizationMonitor.objects.get(
            id=id, organization=user.organization
        )
        monitor = organization_monitor.monitor
        runner_type = (
            infer_context_from_query(organization_monitor.query)
            if organization_monitor.query
            else monitor.runner_type
        )
        if monitor.is_custom() and runner_type != monitor.runner_type:
            monitor.runner_type = runner_type
            monitor.save()
        asyn_run(organization_monitor, user)
        return ExecuteOrganizationMonitor(organization_monitor=organization_monitor)


class UpdateMonitor(graphene.Mutation):
    organization_monitor = graphene.Field(OrganizationMonitorType)

    class Arguments:
        id = graphene.String(required=True)
        description = graphene.String()
        name = graphene.String()
        query = graphene.String()

    @laika_service(
        atomic=False,
        permission='monitor.change_monitor',
        exception_msg='Failed to execute monitor',
    )
    def mutate(self, info, id, **kwargs):
        monitor = Monitor.objects.get(id=id)
        organization = info.context.user.organization
        organization_monitor = OrganizationMonitor.objects.get(
            monitor=monitor,
            organization=organization,
        )
        query = kwargs.get('query')
        if (
            query
            and monitor.monitor_type == MonitorType.SYSTEM
            and not compatible_queries(monitor.query, query)
        ):
            new_monitor = clone_monitor(organization, monitor)
            organization_monitor = clone_organization_monitor(
                organization_monitor, new_monitor
            )
        OrganizationMonitor.objects.filter(id=organization_monitor.id).update(**kwargs)
        organization_monitor.refresh_from_db()
        return UpdateMonitor(organization_monitor=organization_monitor)


MonitorSubscriptionEventEnum = graphene.Enum(
    'EventType', MonitorSubscriptionEventType.choices
)


class BulkWatchMonitors(graphene.Mutation):
    event_type = graphene.String()

    class Arguments:
        input = BulkWatchInput(required=True)

    @laika_service(
        permission='user.view_user', exception_msg='Failed to execute bulk watch update'
    )
    def mutate(self, info, input=None, **kwargs):
        event_type = input.get('event_type').lower()
        ids = input.get('ids')
        current_user = info.context.user
        organization = current_user.organization
        watcher_lists = WatcherList.objects.filter(
            organization=organization, organization_monitor__id__in=ids
        ).prefetch_related('users')
        for watcher_list in watcher_lists:
            if event_type == WATCH:
                watcher_list.users.add(current_user)
            else:
                watcher_list.users.remove(current_user)
        return BulkWatchMonitors(event_type=event_type.capitalize())


class SubscribeToMonitors(graphene.Mutation):
    event_type = graphene.Field(MonitorSubscriptionEventEnum)

    class Arguments:
        event_type = graphene.Argument(MonitorSubscriptionEventEnum)

    @laika_service(
        permission='user.view_user', exception_msg='Failed to load watcher black list'
    )
    def mutate(self, info, **kwargs):
        current_user = info.context.user
        organization = current_user.organization
        event_type = kwargs.get('event_type').lower()
        MonitorSubscriptionEvent.objects.update_or_create(
            user=current_user,
            organization=organization,
            defaults={'event_type': event_type},
        )
        if event_type == MonitorSubscriptionEventType.SUBSCRIBED:
            assign_user_to_watcher_lists_in_organization(
                current_user.id, organization.id
            )
        else:
            remove_user_from_watcher_lists_in_organization(current_user.id)
        return SubscribeToMonitors(event_type=event_type.capitalize())


def clone_monitor(
    organization: Organization,
    monitor: Monitor,
) -> Monitor:
    fields = {
        **clone_model_attributes(monitor),
        'parent_monitor_id': monitor.id,
        'organization_id': organization.id,
        'monitor_type': MonitorType.CUSTOM,
    }
    return Monitor.objects.create(**fields)


def clone_organization_monitor(
    organization_monitor: OrganizationMonitor, new_monitor: Monitor
) -> OrganizationMonitor:
    organization_monitor.monitor = new_monitor
    organization_monitor.save()
    return organization_monitor


def clone_model_attributes(model):
    cloned_attributes = {
        k: v for k, v in model.__dict__.items() if k not in ['_state', 'id']
    }
    return cloned_attributes


def update_status(updated: Result, last_result: MonitorResult):
    updated_status = updated.status(last_result.health_condition)
    last_result.result = updated.to_json()
    if updated_status != last_result.status:
        last_result.status = updated_status
        organization_monitor = last_result.organization_monitor
        organization_monitor.status = last_result.status
        organization_monitor.save()
    last_result.save()


def store_create_event(instance: MonitorExclusion, user: User):
    MonitorExclusionEvent.objects.create(
        monitor_exclusion=instance,
        justification=instance.justification,
        event_date=instance.exclusion_date,
        event_type=MonitorExclusionEventType.CREATED,
        user=user,
    )

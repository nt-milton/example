from datetime import datetime

from django.utils import timezone

from monitor.models import (
    Monitor,
    MonitorExclusion,
    MonitorExclusionEvent,
    MonitorExclusionEventType,
    MonitorFrequency,
    MonitorHealthCondition,
    MonitorInstanceStatus,
    MonitorResult,
    MonitorRunnerType,
    MonitorStatus,
    MonitorType,
    MonitorUserEvent,
    MonitorUserEventsOptions,
    OrganizationMonitor,
)
from organization.tests import create_organization
from program.models import SubTask

MONITOR_RESULT = {
    'data': [[0, 'test'], [1, 'test1'], [2, 'test2']],
    'columns': ['id', 'name'],
    'excluded_results': {'1': {'value': [3, 'test3'], 'variables': {}}},
    'variables': [
        {
            'id': 0,
            'name': 'test',
            'organization_organization.id': 0,
        },
        {
            'id': 1,
            'name': 'test1',
            'organization_organization.id': 1,
        },
        {
            'id': 2,
            'name': 'test2',
            'organization_organization.id': 2,
        },
        {
            'id': 3,
            'name': 'test3',
            'organization_organization.id': 3,
        },
    ],
}


def create_monitor(
    name,
    query,
    validation_query=None,
    description=None,
    monitor_type=MonitorType.SYSTEM,
    status=MonitorStatus.ACTIVE,
    health_condition=MonitorHealthCondition.RETURN_RESULTS,
    frequency=MonitorFrequency.DAILY,
    runner_type=MonitorRunnerType.LAIKA_CONTEXT,
    **kwargs,
):
    if not description:
        description = f'{name} test'

    monitor = Monitor.objects.create(
        name=name,
        query=query,
        validation_query=validation_query,
        description=description,
        monitor_type=monitor_type,
        status=status,
        health_condition=health_condition,
        frequency=frequency,
        runner_type=runner_type,
        source_systems=[
            'asana',
            'aws',
            'google_cloud_platform',
            'app_policies',
            'app_people',
            'lo_users',
            'lo_change_requests',
        ],
        **kwargs,
    )
    return monitor


def create_organization_monitor(
    organization=None,
    monitor=None,
    active=True,
    status=MonitorInstanceStatus.HEALTHY,
    name='',
    description='',
    query='',
    created_at=timezone.now(),
    toggled_by_system=True,
):
    if not organization:
        organization = create_organization(name='organization')
    if not monitor:
        monitor = create_monitor(
            name='Monitor test', query='SELECT id FROM users, users WHERE id=1'
        )

    organization_monitor = OrganizationMonitor.objects.create(
        name=name,
        description=description,
        query=query,
        organization=organization,
        monitor=monitor,
        active=active,
        status=status,
        created_at=created_at,
        toggled_by_system=toggled_by_system,
    )
    return organization_monitor


def create_monitor_result(
    created_at=None,
    organization_monitor=None,
    result=None,
    status=MonitorInstanceStatus.HEALTHY,
):
    if not organization_monitor:
        organization_monitor = create_organization_monitor(status=status)
    if not result:
        result = MONITOR_RESULT

    monitor_result = MonitorResult.objects.create(
        organization_monitor=organization_monitor, result=result, status=status
    )
    if created_at:
        monitor_result.created_at = created_at
        monitor_result.save()
    return monitor_result


def create_monitor_exclusion(**kwargs):
    instance = MonitorExclusion.objects.create(**kwargs)
    MonitorExclusionEvent.objects.create(
        monitor_exclusion=instance,
        justification=instance.justification,
        event_type=MonitorExclusionEventType.CREATED,
    )
    return instance


def create_monitor_exclusion_event(monitor_exclusion, user):
    instance = MonitorExclusionEvent.objects.create(
        monitor_exclusion=monitor_exclusion,
        justification=monitor_exclusion.justification,
        event_type=MonitorExclusionEventType.CREATED,
        user=user,
    )
    return instance


def create_subtask(user, task, reference_id=None):
    return SubTask.objects.create(
        text='SubTask 1',
        assignee=user,
        group='Documentation',
        requires_evidence=True,
        task=task,
        due_date=datetime.now(),
        reference_id=reference_id,
    )


def create_monitor_user_event(
    user,
    organization_monitor=None,
    event=MonitorUserEventsOptions.VIEW_DASHBOARD,
):
    return MonitorUserEvent.objects.create(
        user=user, organization_monitor=organization_monitor, event=event
    )

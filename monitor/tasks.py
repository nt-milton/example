import json
import logging
import timeit
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from django.db import DatabaseError, connection
from django.db.models import Max

from laika.celery import app as celery_app
from laika.constants import DAYS_IN_YEAR
from monitor.events import match_any_dependency, org_monitor_match_any
from monitor.models import (
    Monitor,
    MonitorExclusion,
    MonitorExclusionEvent,
    MonitorExclusionEventType,
    MonitorInstanceStatus,
    MonitorStatus,
    MonitorType,
    OrganizationMonitor,
)
from monitor.result import Result
from monitor.runner import NO_DATASOURCE_RESULT, dry_run, run, validate_dependencies
from monitor.steampipe import clean_steampipe_environment, create_profiles_for_task
from objects.models import LaikaObjectType
from organization.models import ACTIVE, Organization

logger = logging.getLogger('monitor_tasks')

REVERSIONS_CLEAN_UP_STATEMENT = '''
WITH deleted_revisions AS (
    DELETE FROM reversion_version AS rv
    USING reversion_revision AS rr
    WHERE
        rr.date_created <= NOW() - INTERVAL %s AND
        rr.id = rv.revision_id
    RETURNING rv.revision_id
)
DELETE FROM reversion_revision
WHERE id IN (SELECT * FROM deleted_revisions);
'''


@celery_app.task(name='Reversions clean up')
def reversions_clean_up(keep_months: int) -> dict:
    start_time = timeit.default_timer()
    interval = f'{keep_months} months'
    logger.info('Reversions clean up running')
    with connection.cursor() as cursor:
        cursor.execute(REVERSIONS_CLEAN_UP_STATEMENT, [interval])
    logger.info('Reversions clean up done')
    execution_time = timeit.default_timer() - start_time
    return {'execution_time': execution_time}


UPDATED_RESOURCES_QUERY = '''
SELECT dct.app_label || '_' || dct.model AS model, u.organization_id
FROM reversion_version AS rv
LEFT JOIN reversion_revision AS rr ON rr.id = rv.revision_id
LEFT JOIN user_user AS u ON u.id = rr.user_id
LEFT JOIN django_content_type AS dct ON dct.id = rv.content_type_id
LEFT JOIN organization_organization as o ON u.organization_id = o.id
WHERE
u.organization_id IS NOT NULL AND
o.state = 'ACTIVE' AND
dct.app_label || '_' || dct.model IN (
    'audit_audit', 'audit_auditauditor', 'audit_auditfirm', 'control_control',
    'control_controltag', 'dashboard_actionitem', 'fieldwork_attachment',
    'fieldwork_evidence', 'fieldwork_requirement',
    'fieldwork_requirementevidence', 'monitor_monitor',
    'monitor_monitorresult', 'monitor_organizationmonitor', 'policy_policy',
    'policy_policytag', 'policy_publishedpolicy', 'program_program',
    'program_subtask', 'program_task', 'tag_tag', 'training_alumni',
    'training_training', 'user_officer', 'user_team', 'user_teammember',
    'user_user'
)
AND rr.date_created >= now() - interval '5 minutes'
GROUP BY rv.content_type_id, u.organization_id, dct.app_label, dct.model;
'''

CONTENT_TYPE_PER_DEPENDENCIES = {
    'action_items_dependency': {'dashboard_actionitem'},
    'officers_dependency': {'user_officer'},
    'people_dependency': {'user_user'},
    'teams_dependency': {'user_team'},
    'tasks_dependency': {'program_task', 'program_program'},
    'training_alumni_dependency': {'training_alumni', 'training_training'},
    'trainings_dependency': {'training_alumni', 'training_training'},
    'team_members_dependency': {'user_teammember', 'user_team', 'user_user'},
    'audits_dependency': {'audit_audit', 'audit_auditauditor', 'audit_auditfirm'},
    'controls_dependency': {'control_controltag', 'tag_tag', 'control_control'},
    'monitors_dependency': {
        'monitor_organizationmonitor',
        'monitor_monitor',
        'monitor_monitorresult',
    },
    'subtasks_dependency': {
        'program_subtask',
        'program_task',
        'program_program',
    },
    'policies_dependency': {
        'policy_policytag',
        'tag_tag',
        'policy_policy',
        'policy_publishedpolicy',
    },
    'evidence_requests_dependency': {
        'fieldwork_evidence',
        'audit_audit',
        'fieldwork_requirementevidence',
        'fieldwork_requirement',
        'fieldwork_attachment',
    },
}


def _map_types_to_deps() -> dict[str, set[str]]:
    content_types_map = defaultdict(set)
    for dependency, content_types in CONTENT_TYPE_PER_DEPENDENCIES.items():
        for content_type in content_types:
            content_types_map[content_type].add(dependency)
    return content_types_map


DEPENDENCIES_PER_CONTENT_TYPE = _map_types_to_deps()


@celery_app.task(name='refresh_monitors_on_resources_events')
def refresh_monitors_on_resources_events():
    logger.info('Refreshing monitors based on resources events')
    with connection.cursor() as cursor:
        cursor.execute(UPDATED_RESOURCES_QUERY)
        resource_events = cursor.fetchall()
        organization_dependencies = defaultdict(set)
        for content_type, organization_id in resource_events:
            organization_dependencies[organization_id].update(
                DEPENDENCIES_PER_CONTENT_TYPE[content_type]
            )
        for organization_id, dependencies in organization_dependencies.items():
            organization = Organization.objects.get(id=organization_id)
            create_monitors_and_run(organization, dependencies)


RESTART_DELTA = 25


@celery_app.task(name='update_monitors')
def update_monitors() -> dict:
    logger.info('Update monitors job')
    start_time = timeit.default_timer()
    metrics: dict = {}
    organizations = Organization.objects.filter(state=ACTIVE)
    metrics['time_per_org'] = {}
    for organization in organizations:
        clean_steampipe_environment()
        create_profiles_for_task(organization.id)
        organization_run_start = timeit.default_timer()
        logger.info(f'Refresh monitors for org_id: {organization.id}')
        create_monitors_and_run(organization)
        organization_run_time = timeit.default_timer() - organization_run_start
        logger.info(
            f'Refresh for monitor in organization: {organization.id} '
            f'took {organization_run_time}'
        )
        metrics['time_per_org'][str(organization.id)] = organization_run_time
    logger.info('Cleaning monitor exclusions')
    clear_monitor_exclusions()
    execution_time = timeit.default_timer() - start_time
    metrics['execution_time'] = execution_time
    return metrics


@celery_app.task(name='update_monitors_by_org')
def update_monitors_by_org(id: str):
    clean_steampipe_environment()
    create_profiles_for_task(id)
    create_monitors_and_run(Organization.objects.get(id=id))


def create_monitors_and_run(organization: Organization, dependencies: set[str] = None):
    if organization.state == ACTIVE:
        create_missing_monitors(organization, dependencies=dependencies)
        run_monitors(organization.id, dependencies=dependencies)


def active_system_monitors():
    monitors = Monitor.objects.filter(
        status=MonitorStatus.ACTIVE, monitor_type=MonitorType.SYSTEM
    )
    return monitors


def create_missing_monitors(
    organization: Organization, dependencies: Optional[set[str]] = None
):
    monitors = active_system_monitors()
    monitor_ids = [monitor.id for monitor in monitors]
    existing_monitors = find_existing_monitors(organization, monitor_ids)
    exclude_monitors = find_system_monitors_with_child(organization, monitor_ids).union(
        existing_monitors
    )
    candidate_monitors = [
        monitor for monitor in monitors if monitor.id not in exclude_monitors
    ]
    if dependencies:
        candidate_monitors = match_any_dependency(candidate_monitors, dependencies)
    for monitor in candidate_monitors:
        create_organization_monitor(organization, monitor)


def find_system_monitors_with_child(organization: Organization, monitor_ids: list[int]):
    custom_monitors = OrganizationMonitor.objects.filter(
        monitor__parent_monitor_id__in=monitor_ids, organization=organization
    ).values_list('monitor__parent_monitor_id', flat=True)
    return custom_monitors


def find_existing_monitors(organization, monitor_ids):
    existing_monitors = OrganizationMonitor.objects.filter(
        monitor_id__in=monitor_ids, organization=organization
    ).values_list('monitor_id', flat=True)
    return existing_monitors


def create_organization_monitor(organization, monitor):
    try:
        if validate_dependencies(organization, monitor.validation_query):
            OrganizationMonitor.objects.create(
                monitor=monitor,
                organization=organization,
                active=True,
                status=MonitorInstanceStatus.HEALTHY,
            )
    except (DatabaseError, LaikaObjectType.DoesNotExist) as exc:
        logger.warning(
            'Error validating monitor dependencies organization: '
            f'{organization.id} monitor: {monitor.id} {exc}'
        )


def run_monitors(organization_id: str, dependencies=None):
    organization_monitors = active_organization_monitors(organization_id)
    if dependencies:
        organization_monitors = org_monitor_match_any(
            organization_monitors, dependencies
        )
    for organization_monitor in organization_monitors:
        logger.info(f'Run organization_monitor: {organization_monitor.id}')
        run(organization_monitor)


def active_organization_monitors(organization_id):
    return OrganizationMonitor.objects.filter(
        organization_id=organization_id, active=True
    ).iterator()


def clear_monitor_exclusions():
    delta = datetime.now() - timedelta(days=DAYS_IN_YEAR)
    deleted_ids = list(
        MonitorExclusionEvent.objects.filter(
            event_type=MonitorExclusionEventType.DELETED
        )
        .annotate(last_event=Max('event_date'))
        .values_list('monitor_exclusion__id', flat=True)
        .filter(last_event__lt=delta)
    )

    MonitorExclusionEvent.objects.filter(monitor_exclusion__id__in=deleted_ids).delete()
    MonitorExclusion.objects.filter(is_active=False, id__in=deleted_ids).delete()
    logger.info(f'Deleting monitor exclusions {deleted_ids}')


def _read_monitors():
    with open(Path(__file__).parent / 'tests/monitor_list.json') as file:
        return json.load(file)


def _dry_run(org: Organization, monitor: dict) -> Result:
    validation_query = monitor['validation_query']
    query = monitor['query']
    runner_type = monitor['runner_type']
    return dry_run(org, query, validation_query, runner_type)


@celery_app.task(name='validate_monitors')
def validate_monitors(org_id: str) -> dict:
    start = timeit.default_timer()
    organization = Organization.objects.filter(id=org_id).first()
    clean_steampipe_environment()
    create_profiles_for_task(organization.id)
    errors = []
    no_apply = []
    for monitor in _read_monitors():
        result = _dry_run(organization, monitor)
        if result.error:
            errors.append((monitor['name'], result.error))
        elif result == NO_DATASOURCE_RESULT:
            no_apply.append(monitor['name'])
    return {
        'errors': {'total': len(errors), 'monitors': errors},
        'no_apply': {'total': len(no_apply), 'monitors': no_apply},
        'total': timeit.default_timer() - start,
    }

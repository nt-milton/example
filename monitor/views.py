import csv
import json
import logging
from typing import Any, Iterable, List
from uuid import uuid4

from django.contrib import messages
from django.contrib.admin import helpers
from django.contrib.auth.decorators import login_required as django_login_required
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from openpyxl import Workbook

from laika.auth import login_required
from laika.utils.dates import YYYYMMDD, now_date
from laika.utils.spreadsheet import CONTENT_TYPE
from monitor.constants import EMPTY_RESULTS, RETURN_RESULTS
from monitor.export import build_workbook_sheet, create_workbook, save_virtual_workbook
from monitor.models import (
    Monitor,
    MonitorResult,
    OrganizationMonitor,
    infer_context_from_query,
)
from monitor.mutations import clone_monitor, clone_organization_monitor
from monitor.runner import asyn_task, dry_run
from monitor.timeline import Interval
from monitor.types import get_timeline
from organization.models import Organization

from .forms import SendDryRunRequest

CSV_FORMAT = 'csv'
ORGANIZATION_MONITOR_TEMPLATES = 'admin/monitor/organizationmonitor'

logger = logging.getLogger(__name__)


def DuplicateOrganizationMonitorView(request):
    if request.method == 'POST' and 'apply' in request.POST:
        organization_id = request.POST['organization']
        organization = Organization.objects.filter(id=organization_id).first()
        monitor_id = request.POST['monitor']
        monitor = Monitor.objects.filter(id=monitor_id).first()
        new_monitor = clone_monitor(organization, monitor)
        new_monitor.name = request.POST['name']
        new_monitor.query = request.POST['query']
        new_monitor.description = request.POST['description']
        new_monitor.save()
        old_organization_monitor = OrganizationMonitor.objects.filter(
            organization=organization,
            monitor=monitor,
        ).first()
        if old_organization_monitor:
            clone_organization_monitor(old_organization_monitor, new_monitor)
        else:
            OrganizationMonitor.objects.create(
                organization=organization, monitor=new_monitor, active=True
            )
        success_msg = f'Organization monitor {monitor} duplicated successfully'
        messages.success(request, success_msg)
    return redirect('monitor/monitor/')


@csrf_exempt
@login_required
def export_monitor(request):
    body = json.loads(request.body)
    timelapse = body['timelapse']
    monitor = body['monitor']
    file_format = body['format']
    organization_monitor_id = body['organizationMonitorId']
    tags = body['tags']
    org_monitor = OrganizationMonitor.objects.get(id=organization_monitor_id)
    monitor_results = MonitorResult.objects.filter(
        organization_monitor=org_monitor
    ).order_by('id')
    timeline = get_timeline(monitor_results, timelapse).build()
    if file_format == CSV_FORMAT:
        return write_csv(monitor, timeline, tags)
    else:
        return write_xls(monitor, timeline, tags)


def remove_brackets(elements: Iterable[str]):
    return str(elements)[1:-1]


def get_health_history_columns() -> list[str]:
    return [
        'Monitor Name',
        'Description',
        'Tags',
        'Urgency',
        'Control References',
        'Run Timestamp',
        'Health',
        'Healthy If',
        'Query',
    ]


def get_health_history_data(
    timeline: list[Interval], monitor: dict, tags: list[dict]
) -> Iterable[List[Any]]:
    result = []
    for day in reversed(timeline):
        query = day.query or monitor['query']
        health_condition = day.health_condition or monitor['healthCondition']
        result.append(
            [
                monitor['name'],
                monitor['description'],
                remove_brackets([t['name'] for t in tags]),
                monitor['urgency'],
                remove_brackets(monitor['controlReferences'].splitlines()),
                day.start,
                day.status,
                RETURN_RESULTS
                if health_condition == 'return_results'
                else EMPTY_RESULTS,
                ' '.join(line.strip() for line in query.splitlines()),
            ]
        )
    return result


def write_csv(monitor: dict, timeline: list[Interval], tags: list[dict]):
    response = HttpResponse(content_type='text/csv')
    writer = csv.writer(response)
    writer.writerow(get_health_history_columns())
    for row in get_health_history_data(timeline, monitor, tags):
        writer.writerow(row)
    return response


def write_xls(monitor: dict, timeline: list[Interval], tags: list[dict]):
    response = HttpResponse(content_type='text/xlsx')
    workbook = Workbook()
    build_workbook_sheet(
        workbook,
        get_health_history_columns(),
        get_health_history_data(timeline, monitor, tags),
        monitor['name'],
    )
    workbook.save(response)
    return response


def str_bool_to_python_bool(condition: str):
    if condition is None:
        return True
    formatted_condition = condition.strip().lower()
    if formatted_condition == 'true':
        return True
    elif formatted_condition == 'false':
        return False


@csrf_exempt
@login_required
def export_monitor_results(request, org_monitor_id: str) -> HttpResponse:
    timezone = request.GET.get('timezone')
    include_unfiltered = str_bool_to_python_bool(request.GET.get('includeUnfiltered'))
    metadata = str_bool_to_python_bool(request.GET.get('metadata'))
    limit = request.GET.get('limit')
    validate_mandatory_parameters(org_monitor_id=org_monitor_id, timezone=timezone)
    org_monitor = OrganizationMonitor.objects.get(id=org_monitor_id)
    validate_organizations_match(request.user.organization, org_monitor.organization)
    return build_export_file(org_monitor, include_unfiltered, metadata, limit, timezone)


def build_export_file(org_monitor, include_unfiltered, metadata, limit, timezone):
    workbook = create_workbook(org_monitor, include_unfiltered, limit)
    response = HttpResponse(
        content=save_virtual_workbook(workbook), content_type=CONTENT_TYPE
    )
    date = now_date(timezone, YYYYMMDD)
    filename = f'{org_monitor.monitor.name}-{date}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def validate_mandatory_parameters(**kwargs):
    if None in kwargs.values():
        return HttpResponseBadRequest()


def validate_organizations_match(
    user_organization: Organization, request_organization: Organization
):
    if user_organization != request_organization:
        return HttpResponse('Unauthorized', status=401)


@csrf_exempt
@django_login_required
def GetDryRunResult(request) -> HttpResponse:
    context_id = request.GET.get('context_id')
    results = cache.get(context_id)
    if results:
        return render(
            request,
            f'{ORGANIZATION_MONITOR_TEMPLATES}/dry_run_completed_result.html',
            context={'results': results},
        )
    elif results is not None:
        return render(
            request, f'{ORGANIZATION_MONITOR_TEMPLATES}/dry_run_pending_result.html'
        )
    else:
        messages.error(request, f'Dry run request {context_id} does not exist')
        return redirect('/admin/monitor/organizationmonitor')


def _build_dry_run_context(
    context_id: str,
    organization: Organization,
    query: str,
    validation_query: str,
    health_condition: str,
):
    runner_type = infer_context_from_query(query)
    result = dry_run(organization, query, validation_query, runner_type)
    context = {
        'id': 'N/A',
        'name': 'N/A',
        'query': query,
        'original_query': 'N/A',
        'validation_query': validation_query,
        'runner_type': runner_type,
        'result': result.to_json(),
        'health_condition': result.status(health_condition),
    }
    cache.set(context_id, [context])


@csrf_exempt
@django_login_required
def RequestDryRun(request) -> HttpResponse:
    context_id = str(uuid4())
    cache.set(context_id, {})
    organization_id = request.POST.get('organization')
    organization = Organization.objects.get(id=organization_id)
    query = request.POST.get('query')
    validation_query = request.POST.get('validation_query')
    health_condition = request.POST.get('health_condition')
    asyn_task(
        _build_dry_run_context,
        context_id,
        organization,
        query,
        validation_query,
        health_condition,
    )
    return redirect(f'/admin/monitor/dry_run?context_id={context_id}')


@csrf_exempt
@django_login_required
def GetMonitorPlayground(request) -> HttpResponse:
    form = SendDryRunRequest()
    return render(
        request,
        'admin/monitor/organizationmonitor/monitor_playground.html',
        context={
            'form': form,
            'adminform': helpers.AdminForm(
                form,
                [(None, {'fields': form.base_fields})],
                {},
            ),
        },
    )

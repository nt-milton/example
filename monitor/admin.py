import logging
from uuid import uuid4

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.core.cache import cache
from django.db.models.query import QuerySet
from django.forms import forms
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path
from django.views.decorators.http import require_GET, require_POST
from reversion.admin import VersionAdmin

from . import template
from .export import export_monitors, import_monitors
from .forms import DuplicateMonitorForm, MonitorAdminForm, OrganizationMonitorAdminForm
from .models import (
    Monitor,
    MonitorExclusion,
    MonitorExclusionEvent,
    MonitorExclusionEventType,
    MonitorResult,
    MonitorType,
    OrganizationMonitor,
)
from .runner import asyn_task, dry_run, run

logger = logging.getLogger(__name__)

CLONE_AS_CUSTOM_MONITOR = 'Clone as custom monitor'


class JsonImportForm(forms.Form):
    json_file = forms.FileField()


class MonitorAdmin(VersionAdmin):
    readonly_fields = ('runner_type',)
    list_display = (
        'id',
        'name',
        'display_id',
        'urgency',
        'query',
        'status',
        'health_condition',
        'runner_type',
        'monitor_type',
        'frequency',
        'parent_monitor',
        'organization',
    )
    list_filter = (
        'status',
        'urgency',
        'health_condition',
        'runner_type',
        'monitor_type',
        'frequency',
        'parent_monitor',
        'organization',
    )
    search_fields = ['name', 'query']
    ordering = (
        'id',
        'name',
        'status',
        'health_condition',
        'runner_type',
        'monitor_type',
        'frequency',
        'parent_monitor',
    )
    actions = ['duplicate_record', 'export']

    form = MonitorAdminForm

    change_list_template = "admin/monitor/monitor_changelist.html"

    def duplicate_record(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, 'Cannot duplicate more than one object at once')
            return
        if queryset[0].monitor_type == MonitorType.CUSTOM:
            self.message_user(request, 'Cannot duplicate a custom monitor')
            return
        monitor_id = queryset.values()[0]['id']
        monitor_data = Monitor.objects.filter(id=monitor_id).values()[0]
        form = DuplicateMonitorForm(
            initial={
                **monitor_data,
                'monitor': monitor_id,
            }
        )
        return render(
            request,
            'admin/duplicate_monitor.html',
            context={
                'title': CLONE_AS_CUSTOM_MONITOR,
                'form': form,
                'adminform': helpers.AdminForm(
                    form,
                    list([(None, {'fields': form.base_fields})]),
                    self.get_prepopulated_fields(request),
                ),
            },
        )

    description = CLONE_AS_CUSTOM_MONITOR
    duplicate_record.short_description = description  # type: ignore

    def export(self, request, queryset):
        system_monitors = [m for m in queryset if m.monitor_type == MonitorType.SYSTEM]
        response = HttpResponse(
            content=export_monitors(system_monitors), content_type='application/json'
        )
        response['Content-Disposition'] = 'attachment; filename=export.json'
        return response

    export.short_description = 'Export JSON'  # type: ignore

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('import-json/import/', import_json),
            path('import-json/', show_import),
        ]
        return my_urls + urls


@require_POST
def import_json(request):
    json = request.FILES['json_file']
    import_monitors(json.read().decode())
    messages.info(request, 'Your json file has been imported')
    return redirect('../..')


@require_GET
def show_import(request):
    payload = {'form': JsonImportForm()}
    return render(request, 'admin/json_form.html', payload)


admin.site.register(Monitor, MonitorAdmin)


class MonitorExclusionEventInline(admin.TabularInline):
    model = MonitorExclusionEvent
    field = ('user', 'event_date', 'event_type', 'justification')
    readonly_fields = ('user', 'event_date', 'event_type', 'justification')
    ordering = ("-event_date",)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


class MonitorExclusionInline(admin.TabularInline):
    model = MonitorExclusion
    fields = (
        'key',
        'value',
        'exclusion_date',
        'justification',
        'is_deleted',
        'record_deprecated',
        'latest_date_updated',
        'snapshot',
    )
    readonly_fields = [
        'exclusion_date',
        'key',
        'value',
        'justification',
        'is_deleted',
        'record_deprecated',
        'latest_date_updated',
        'snapshot',
    ]
    ordering = ("-exclusion_date",)
    show_change_link = True

    def latest_date_updated(self, obj):
        return obj.last_event.event_date

    def is_deleted(self, obj):
        event_type = obj.last_event.event_type
        return event_type == MonitorExclusionEventType.DELETED

    def record_deprecated(self, obj):
        event_type = obj.last_event.event_type
        return event_type == MonitorExclusionEventType.DEPRECATED

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


def _build_dry_run_context(context_id: str, organization_monitors: QuerySet):
    results = []
    for organization_monitor in organization_monitors:
        monitor = organization_monitor.monitor
        original_query = organization_monitor.query or monitor.query
        query = template.build_query_for_variables(
            original_query, monitor.fix_me_link, monitor.exclude_field
        )
        result = dry_run(
            organization_monitor.organization,
            query,
            monitor.validation_query,
            monitor.runner_type,
        )
        results.append(
            {
                'id': organization_monitor.id,
                'name': organization_monitor.name or monitor.name,
                'query': query,
                'original_query': original_query,
                'validation_query': monitor.validation_query,
                'runner_type': monitor.runner_type,
                'result': result.to_json(),
                'health_condition': result.status(monitor.health_condition),
            }
        )
    cache.set(context_id, results)


class OrganizationMonitorAdmin(VersionAdmin):
    list_display = ('organization', 'monitor', 'active', 'status')
    list_filter = ('status', 'active', 'toggled_by_system', 'organization')
    search_fields = ['organization__name', 'monitor__name']
    autocomplete_fields = ['organization', 'monitor']
    actions = ['run_monitor', 'dry_run_monitor']
    readonly_fields = ('controls', 'tags', 'toggled_by_system')
    inlines = [MonitorExclusionInline]
    fieldsets = (
        (
            None,
            {
                'fields': (
                    'organization',
                    'monitor',
                    'watcher_list',
                    'active',
                    'toggled_by_system',
                    'status',
                    'controls',
                    'tags',
                    'urgency',
                ),
            },
        ),
        (
            'Overwrite fields',
            {
                'fields': ('name', 'query', 'description'),
                'description': (
                    'Use these fields to overwrite data without changing the '
                    'original monitor'
                ),
            },
        ),
    )
    form = OrganizationMonitorAdminForm

    def run_monitor(self, request, queryset):
        for org_monitor in queryset:
            run(org_monitor)

    run_monitor.short_description = (  # type: ignore
        'Run the selected monitors (results will be saved)'
    )

    def dry_run_monitor(self, request, queryset):
        context_id = str(uuid4())
        cache.set(context_id, {})
        asyn_task(_build_dry_run_context, context_id, queryset)
        return redirect(f'/admin/monitor/dry_run?context_id={context_id}')

    dry_run_monitor.short_description = (  # type: ignore
        'Dry run the selected monitors (results won\'t be saved)'
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            run(obj)


admin.site.register(OrganizationMonitor, OrganizationMonitorAdmin)


class MonitorResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'organization', 'monitor', 'status')
    list_filter = ('status', 'organization_monitor')
    readonly_fields = ('query', 'health_condition', 'execution_time', 'created_at')
    search_fields = [
        'organization_monitor__organization__name',
        'organization_monitor__monitor__name',
    ]

    def organization(self, obj):
        return obj.organization_monitor.organization.name

    def monitor(self, obj):
        return obj.organization_monitor.monitor


admin.site.register(MonitorResult, MonitorResultAdmin)


class MonitorExclusionAdmin(admin.ModelAdmin):
    fields = (
        'exclusion_date',
        'last_update',
        'organization_monitor',
        'is_active',
        'is_deprecated',
        'key',
        'value',
        'snapshot',
        'justification',
    )
    readonly_fields = ['exclusion_date', 'is_deprecated', 'last_update']
    list_display = ('organization', 'last_update', 'key', 'value', 'justification')
    list_filter = ('key', 'value', 'justification')
    inlines = [MonitorExclusionEventInline]

    def organization(self, obj):
        return obj.organization_monitor.organization.name

    def last_update(self, obj):
        return (
            MonitorExclusionEvent.objects.filter(monitor_exclusion=obj)
            .order_by('-event_date')
            .first()
            .event_date
        )

    def is_deprecated(self, obj):
        return (
            MonitorExclusionEvent.objects.filter(monitor_exclusion=obj)
            .order_by('-event_date')
            .first()
            .event_type
            == MonitorExclusionEventType.DEPRECATED
        )

    def save_model(self, request, obj, form, change):
        user = request.user
        super().save_model(request, obj, form, change)
        MonitorExclusionEvent.objects.create(
            monitor_exclusion_id=obj.id,
            justification=obj.justification,
            event_date=obj.exclusion_date,
            event_type=MonitorExclusionEventType.CREATED,
            user=user,
        )


admin.site.register(MonitorExclusion, MonitorExclusionAdmin)

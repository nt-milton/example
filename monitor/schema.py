import logging

import graphene
from django.db.models import BooleanField, Case, Max, Value, When

from laika.auth import login_required
from laika.decorators import laika_service
from laika.types import FiltersType, OrderInputType, PaginationInputType
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.paginator import get_paginated_result
from monitor.export import get_latest_result
from organization.models import Organization
from user.models import User

from . import template
from .constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from .data_loaders import get_new_org_monitors
from .exclusion import expand_result_with_exclusion, load_exclusions, load_last_events
from .filters import get_monitor_filters, get_monitor_query
from .models import MonitorExclusion, OrganizationMonitor, infer_context_from_query
from .mutations import (
    AddCustomMonitorWithoutParent,
    AddUserMonitorEvent,
    BulkWatchMonitors,
    CreateMonitorExclusion,
    ExecuteOrganizationMonitor,
    RevertMonitorExclusion,
    SubscribeToMonitors,
    UpdateMonitor,
    UpdateMonitorExclusion,
    UpdateOrganizationMonitor,
)
from .order_queries import build_list_of_order_queries, build_order_queries
from .runner import build_unfiltered_query, dry_run
from .types import (
    ControlMonitorsResponseType,
    ControlStatsType,
    ExcludedResultType,
    MonitorExclusionResultType,
    MonitorsWatchersType,
    OrganizationMonitorsResponseType,
    OrganizationMonitorType,
    QueryExecution,
)

logger = logging.getLogger('Monitor')

UNASSIGNED_WATCHER = '-1'


class Mutation(object):
    update_organization_monitor = UpdateOrganizationMonitor.Field()
    execute_organization_monitor = ExecuteOrganizationMonitor.Field()
    update_monitor = UpdateMonitor.Field()
    add_custom_monitor_without_parent = AddCustomMonitorWithoutParent.Field()
    create_monitor_exclusion = CreateMonitorExclusion.Field()
    update_monitor_exclusion = UpdateMonitorExclusion.Field()
    revert_monitor_exclusion = RevertMonitorExclusion.Field()
    add_user_monitor_event = AddUserMonitorEvent.Field()
    subscribe_to_monitors = SubscribeToMonitors.Field()
    bulk_watch_monitors = BulkWatchMonitors.Field()


class Query(object):
    organization_monitors = graphene.Field(
        OrganizationMonitorsResponseType,
        order_by=graphene.Argument(graphene.List(OrderInputType), required=False),
        pagination=graphene.Argument(PaginationInputType, required=False),
        filter=graphene.JSONString(required=False),
        search_criteria=graphene.String(required=False),
    )
    organization_monitor = graphene.Field(
        OrganizationMonitorType, id=graphene.String(), timelapse=graphene.Int()
    )
    control_monitors = graphene.Field(
        ControlMonitorsResponseType,
        order_by=graphene.Argument(graphene.List(OrderInputType), required=False),
        pagination=graphene.Argument(PaginationInputType, required=False),
        filter=graphene.JSONString(required=False),
    )
    unfiltered_organization_monitor_result = graphene.Field(
        QueryExecution,
        organization_monitor_id=graphene.ID(required=True),
        limit=graphene.Int(required=True),
    )
    dry_query_run = graphene.Field(
        QueryExecution,
        query=graphene.String(required=True),
    )
    monitor_exclusions = graphene.Field(
        MonitorExclusionResultType,
        organization_monitor_id=graphene.ID(required=True),
    )
    organization_monitor_excluded_results = graphene.Field(
        ExcludedResultType,
        organization_monitor_id=graphene.ID(required=True),
    )
    monitors_watchers = graphene.Field(MonitorsWatchersType)
    monitors_filters = graphene.List(FiltersType)

    @laika_service(
        permission='monitor.view_monitor',
        exception_msg='Failed to get exclusion results for monitor',
    )
    def resolve_organization_monitor_excluded_results(self, info, **kwargs):
        organization_monitor_id = kwargs.get('organization_monitor_id')
        organization_monitor = OrganizationMonitor.objects.get(
            organization=info.context.user.organization, id=organization_monitor_id
        )
        last_result = get_latest_result(organization_monitor)
        new_columns = [
            'Excluded By',
            'Excluded Date',
            'Last Updated',
            'Justification',
            *last_result['columns'],
        ]
        excluded_results = last_result.get('excluded_results', {})
        exclusions = load_exclusions(list(excluded_results.keys()))
        last_events = load_last_events(list(excluded_results.keys()))
        new_data = expand_result_with_exclusion(
            excluded_results, exclusions, last_events
        )

        sorted_result = (excluded_results.get(str(e.id), {}) for e in exclusions)
        variables = [
            value.get('variables') for value in sorted_result if hasattr(value, 'get')
        ]
        fix_me_links_data = {'data': excluded_results, 'variables': variables}
        fix_me_links = template.build_fix_links(
            organization_monitor,
            fix_me_links_data,
        )
        return ExcludedResultType(
            columns=new_columns,
            data=new_data,
            exclusion_ids=[e.id for e in exclusions],
            fix_me_links=fix_me_links,
        )

    @laika_service(
        permission='monitor.view_monitor',
        exception_msg='Failed to get exclusion criteria for monitor',
    )
    def resolve_monitor_exclusions(self, info, **kwargs):
        organization_monitor_id = kwargs.get('organization_monitor_id')
        organization_monitor = OrganizationMonitor.objects.get(
            id=organization_monitor_id, organization=info.context.user.organization
        )
        monitor_exclusions = MonitorExclusion.objects.filter(
            organization_monitor=organization_monitor,
            is_active=True,
        )
        return MonitorExclusionResultType(monitor_exclusions=monitor_exclusions)

    @laika_service(
        permission='monitor.view_monitor',
        exception_msg='Failed to execute dry run on organization monitor',
    )
    def resolve_dry_query_run(self, info, **kwargs):
        organization = info.context.user.organization
        query = kwargs.get('query')
        runner_type = infer_context_from_query(query)
        result = dry_run(organization, query, '', runner_type).to_json()
        return QueryExecution(result=result)

    @laika_service(
        permission='monitor.view_monitor',
        exception_msg='Failed to execute dry run on organization monitor',
    )
    def resolve_unfiltered_organization_monitor_result(self, info, **kwargs):
        organization_monitor_id = kwargs.get('organization_monitor_id')
        organization_monitor = OrganizationMonitor.objects.get(
            id=organization_monitor_id, organization=info.context.user.organization
        )
        organization = organization_monitor.organization
        monitor = organization_monitor.monitor
        limit = kwargs.get('limit')
        query = template.build_query_for_variables(
            build_unfiltered_query(monitor.query, limit),
            monitor.fix_me_link,
            monitor.exclude_field,
        )

        result = template.extract_placeholders(
            dry_run(organization, query, monitor.validation_query, monitor.runner_type)
        ).to_json()
        fix_me_links = template.build_fix_links(organization_monitor, result)
        return QueryExecution(result=result, fix_me_links=fix_me_links)

    @laika_service(
        permission='monitor.view_monitor', exception_msg='Failed to list monitors'
    )
    def resolve_organization_monitors(self, info, **kwargs):
        filter_args = kwargs.get('filter', {})
        search_criteria = kwargs.get('search_criteria', {})

        filter_params = get_monitor_query(
            info.context.user.organization_id, filter_args, search_criteria
        )

        order_by = kwargs.get(
            'order_by',
            [
                {'field': 'status', 'order': 'descend'},
            ],
        )
        if order_by[0]['field'] == 'status':
            order_by = [
                {'field': 'active', 'order': 'descend'},
                {'field': 'status', 'order': order_by[0]['order']},
                {'field': 'is_viewed', 'order': 'descend'},
                {'field': 'monitor__source_systems', 'order': 'ascend'},
                {'field': 'monitor__name', 'order': 'ascend'},
            ]
        order_queries = build_list_of_order_queries(order_by)

        current_user = info.context.user
        new_org_monitors = get_new_org_monitors(current_user)
        org_monitors_watched_by_current_user = [
            watcher_list.organization_monitor.id
            for watcher_list in current_user.watchers.filter(
                organization_monitor__isnull=False
            )
        ]
        org_monitors = (
            OrganizationMonitor.objects.filter(filter_params)
            .annotate(
                last_run=Max('monitorresult__created_at'),
                is_user_watching=Case(
                    When(id__in=org_monitors_watched_by_current_user, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
                is_viewed=Case(
                    When(id__in=new_org_monitors, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
            )
            .order_by(*order_queries)
        )
        pagination = kwargs.get('pagination')
        page = pagination.page if pagination else DEFAULT_PAGE
        page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE
        paginated_result = get_paginated_result(org_monitors, page_size, page)

        return OrganizationMonitorsResponseType(
            all_ids=org_monitors.values_list('id', flat=True),
            results=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @laika_service(
        permission='monitor.view_monitor', exception_msg='Failed to list monitors'
    )
    def resolve_organization_monitor(self, info, **kwargs):
        id = kwargs.get('id')
        if not id:
            return None

        return OrganizationMonitor.objects.get(
            organization_id=info.context.user.organization_id, monitor__id=id
        )

    @laika_service(
        permission='monitor.view_monitor',
        exception_msg='Failed to list control associated monitors',
    )
    def resolve_control_monitors(self, info, **kwargs):
        filter_params = {'organization_id': info.context.user.organization_id}
        order_by = [
            {'field': 'active', 'order': 'descend'},
            {'field': 'status', 'order': 'descend'},
            {'field': 'id', 'order': 'ascend'},
        ]
        filter_by_control_id = kwargs.get('filter', {}).get('controlId')
        filter_by_triggered_monitor = kwargs.get('filter', {}).get('triggered')
        filter_by_connection_error_monitor = kwargs.get('filter', {}).get(
            'connectionError'
        )
        filter_by_active_monitor = kwargs.get('filter', {}).get('active')

        if filter_by_control_id:
            filter_params['controls__id'] = filter_by_control_id

        if filter_by_triggered_monitor and filter_by_connection_error_monitor:
            filter_params['status__in'] = [
                filter_by_triggered_monitor,
                filter_by_connection_error_monitor,
            ]

        if filter_by_active_monitor:
            filter_params['active'] = filter_by_active_monitor

        order_queries = build_order_queries(order_by)

        org_monitors = (
            OrganizationMonitor.objects.filter(**filter_params)
            .annotate(last_run=Max('monitorresult__created_at'))
            .order_by(*order_queries)
        )
        active_monitors = OrganizationMonitor.objects.filter(
            organization_id=info.context.user.organization_id,
            controls__id=filter_by_control_id,
            active=True,
        ).count()
        inactive_monitors = OrganizationMonitor.objects.filter(
            organization_id=info.context.user.organization_id,
            controls__id=filter_by_control_id,
            active=False,
        ).count()

        pagination = kwargs.get('pagination')
        page = pagination.page if pagination else DEFAULT_PAGE
        page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE
        paginated_result = get_paginated_result(org_monitors, page_size, page)

        return ControlMonitorsResponseType(
            results=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
            control_stats=ControlStatsType(
                actives=active_monitors, inactives=inactive_monitors
            ),
        )

    @laika_service(
        permission='monitor.view_monitor', exception_msg='Failed to list watchers'
    )
    def resolve_monitors_watchers(self, info, **kwargs):
        return MonitorsWatchersType(
            watchers=get_watchers(info.context.user.organization)
        )

    @login_required
    def resolve_monitors_filters(self, info, **kwargs):
        return get_monitor_filters(info.context.user.organization)


def get_watchers(organization: Organization):
    return User.objects.filter(watchers__organization=organization).distinct()

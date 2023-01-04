import datetime
import logging

import graphene
from django.db.models import Q

from laika.auth import login_required, permission_required
from laika.types import OrderInputType, PaginationInputType
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.exceptions import service_exception
from laika.utils.paginator import get_paginated_result

from .constants import (
    ARCHIVED,
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    FILTER_DAYS,
    FILTER_SHARING_ACTIVE,
    FILTER_SHARING_INACTIVE,
    FILTER_STATUS,
)
from .models import DaysOrderBy, Report
from .mutations import CreateReport, ToggleReport
from .types import FilterGroupsReports, ReportResponseType, ReportsResponseType

logger = logging.getLogger(__name__)


def create_filter_reports_data():
    return [
        {
            'id': 'time',
            'name': 'By Time',
            'items': [
                {
                    'id': 'last_seven_days',
                    'name': 'Last 7 Days',
                    'sub_items': [],
                    'disabled': False,
                },
                {
                    'id': 'last_month',
                    'name': 'Last Month',
                    'sub_items': [],
                    'disabled': False,
                },
                {
                    'id': 'last_quarter',
                    'name': 'Last Quarter',
                    'sub_items': [],
                    'disabled': False,
                },
            ],
        },
        {
            'id': 'status',
            'name': 'By Status',
            'items': [
                {
                    'id': FILTER_SHARING_ACTIVE,
                    'name': 'Sharing Active',
                    'subItems': [],
                    'disabled': False,
                },
                {
                    'id': FILTER_SHARING_INACTIVE,
                    'name': 'Sharing Inactive',
                    'subItems': [],
                    'disabled': False,
                },
                {'id': ARCHIVED, 'name': 'Archived', 'subItems': [], 'disabled': False},
            ],
        },
    ]


def _if_filter_by_days(filter_query, field, value):
    if field == FILTER_DAYS:
        time_filter = next(
            (
                filter[1]
                for filter in DaysOrderBy.FILTERS.value
                if filter[0] == value.upper()
            ),
            None,
        )

        if field == DaysOrderBy.FIELD.value and time_filter:
            last_updated = Report.objects.all().latest('updated_at')
            d = last_updated.updated_at - datetime.timedelta(days=time_filter)
            filter_query.add(Q(updated_at__gte=d), Q.AND)


def _if_filter_by_archived(filter_query, field, value):
    if field == FILTER_STATUS and value == ARCHIVED:
        filter_query.add(Q(is_deleted=True), Q.AND)
    else:
        filter_query.add(Q(is_deleted=False), Q.AND)


def _if_filter_by_sharing(filter_query, field, value):
    if field == FILTER_STATUS:
        if value == FILTER_SHARING_ACTIVE:
            filter_query.add(Q(link__is_enabled=True), Q.AND)

        if value == FILTER_SHARING_INACTIVE:
            filter_query.add(Q(link__is_enabled=False), Q.AND)


def get_filter_reports(organization, **kwargs):
    filter_by = kwargs.get('filter')
    filter_query = Q()

    reports = Report.objects.all()

    if reports.count() == 0:
        return reports

    if filter_by:
        for field, value in filter_by.items():
            _if_filter_by_days(filter_query, field, value)
            _if_filter_by_archived(filter_query, field, value)
            _if_filter_by_sharing(filter_query, field, value)
    else:
        filter_query.add(Q(is_deleted=False), Q.AND)

    order_by = kwargs.get('order_by')

    return (
        Report.objects.filter(filter_query)
        .filter(owner__organization=organization)
        .sort(order_by)
    )


class Mutation(graphene.ObjectType):
    create_report = CreateReport.Field()
    toggle_report = ToggleReport.Field()


class Query(object):
    reports = graphene.Field(
        ReportsResponseType,
        order_by=graphene.Argument(OrderInputType, required=False),
        pagination=graphene.Argument(PaginationInputType, required=False),
        filter=graphene.JSONString(required=False),
    )

    report = graphene.Field(ReportResponseType, id=graphene.String(required=True))

    filter_groups_reports = graphene.List(FilterGroupsReports, required=True)

    @login_required
    @service_exception('Failed to retrieve reports')
    @permission_required('report.view_report')
    def resolve_reports(self, info, **kwargs):
        organization = info.context.user.organization
        reports = get_filter_reports(organization, **kwargs)
        pagination = kwargs.get('pagination')
        page = pagination.page if pagination else DEFAULT_PAGE
        page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE
        paginated_result = get_paginated_result(reports, page_size, page)

        return ReportsResponseType(
            data=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @login_required
    @service_exception('Failed to get report details. Please try again.')
    def resolve_report(self, info, **kwargs):
        report = Report.objects.get(
            id=kwargs.get('id'),
            owner__organization=info.context.user.organization,
            is_deleted=False,
        )

        return ReportResponseType(data=report)

    @login_required
    @service_exception('Cannot get filter groups')
    @permission_required('report.view_report')
    def resolve_filter_groups_reports(self, info, **kwargs):
        return create_filter_reports_data()

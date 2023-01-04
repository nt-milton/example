import json
import logging
from typing import List

import graphene
from django.db import transaction
from django.db.models import F, Q
from django.db.models.query import Prefetch, QuerySet

from action_item.constants import TYPE_CONTROL, TYPE_POLICY, TYPE_QUICK_START
from action_item.models import ActionItemStatus
from certification.helpers import (
    get_certification_controls,
    get_certification_progress,
    get_required_action_items_completed,
    get_total_required_action_items,
)
from certification.models import UnlockedOrganizationCertification
from control.constants import STATUS
from control.helpers import get_health_stats
from control.models import Control
from dashboard.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from dashboard.models import (
    NON_SUBTYPE_TASK_TYPES,
    ActionItem,
    ActionItemMetadata,
    TaskView,
)
from dashboard.mutations import UpdateDashboardActionItem, UpdateDashboardItem
from dashboard.quicklinks.quick_link_classes import (
    ControlQuickLink,
    IntegrationQuickLink,
    MonitorQuickLink,
    PolicyQuickLink,
    QuickLinkBase,
)
from dashboard.types import (
    ActionItemListResponseType,
    ActionItemResponseType,
    CalendarActionItemResponseType,
    CalendarActionItemType,
    FrameworkCardType,
    PendingItemsResponseType,
    QuickLinkType,
    TaskViewResponseType,
)
from laika.auth import login_required, permission_required
from laika.decorators import laika_service
from laika.types import OrderInputType, PaginationInputType
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.exceptions import format_stack_in_one_line, service_exception
from laika.utils.paginator import get_paginated_result
from program.constants import SUBTASK_COMPLETED_STATUS, SUBTASKS_ACTION_ITEMS_STATUS
from user.constants import USER_ROLES

ACTION_ITEM_INITIAL_STATUS = [ActionItemStatus.NEW, ActionItemStatus.PENDING]

logger = logging.getLogger(__name__)


def filter_by_user(field, value, info):
    if field == 'user' and value:
        return Q(assignee=info.context.user)
    return Q()


def filter_by_date(field, value):
    if field == 'date':
        return Q(due_date=value)
    return Q()


def filter_by_range(field, value):
    if field == 'range':
        date_range = json.loads(value)
        return Q(due_date__range=[date_range.get('start'), date_range.get('end')])
    return Q()


def filter_by_framework(field, certification_code):
    if field == 'framework':
        return (
            Q(reference_id__endswith=certification_code) & Q(type=TYPE_CONTROL)
        ) | Q(reference_id='')
    return Q()


def filter_by_user_role(user):
    if user.role == USER_ROLES['VIEWER'] or user.role == USER_ROLES['SALESPERSON']:
        return Q(type=TYPE_POLICY) | Q(type=TYPE_QUICK_START)
    return Q()


def get_filter_query(filter_by, info):
    filter_query = Q()
    for field, value in filter_by.items():
        filter_query.add(filter_by_user(field, value, info), Q.AND)
        filter_query.add(filter_by_date(field, value), Q.AND)
        filter_query.add(filter_by_range(field, value), Q.AND)
        filter_query.add(filter_by_framework(field, value), Q.AND)

    filter_query.add(filter_by_user_role(info.context.user), Q.AND)

    return filter_query


def get_certification_card_payload(unlocked_certification, organization_id):
    organization_controls_health = Control.controls_health(organization_id)

    certification_controls = get_certification_controls(
        unlocked_certification.certification.sections.all(),
        certification_code=unlocked_certification.certification.code,
    )

    certification_action_items = []
    for cc in certification_controls:
        certification_action_items.extend(cc.action_items.all())

    required_action_items_completed = get_required_action_items_completed(
        certification_action_items
    )
    total_required_action_items = get_total_required_action_items(
        certification_action_items
    )
    progress = get_certification_progress(
        required_action_items_completed, total_required_action_items
    )

    certification_controls_ids = [control.id for control in certification_controls]

    framework_controls_health = {
        control_id: organization_controls_health[control_id]
        for control_id in organization_controls_health
        if control_id in certification_controls_ids
    }
    control_stats = get_health_stats(framework_controls_health)

    operational = control_stats.get('healthy', 0)
    needs_attention = control_stats.get('flagged', 0)
    not_implemented = len(
        [
            control
            for control in certification_controls
            if control.status.upper() == STATUS['NOT IMPLEMENTED']
        ]
    )
    logo = (
        unlocked_certification.certification.logo
        if unlocked_certification.certification
        else None
    )

    return FrameworkCardType(
        id=unlocked_certification.certification.id,
        controls=len(certification_controls),
        framework_name=unlocked_certification.certification.name,
        operational=operational,
        needs_attention=needs_attention,
        not_implemented=not_implemented,
        progress=progress,
        logo_url=logo.url if logo else None,
        sort_index=unlocked_certification.certification.sort_index,
    )


def get_duplicated_control_action_item_ids(control_action_items: QuerySet) -> list:
    unique_action_item_ids = []
    duplicated_control_action_item_ids = []
    for ai in control_action_items:
        if ai.unique_action_item_id not in unique_action_item_ids:
            unique_action_item_ids.append(ai.unique_action_item_id)
            continue
        duplicated_control_action_item_ids.append(ai.id)
    return duplicated_control_action_item_ids


@transaction.atomic
def remove_unassigned_action_items(
    all_action_items_assigned, updated_action_items_assigned, assignee
):
    for existing_ac in all_action_items_assigned:
        if existing_ac not in updated_action_items_assigned:
            try:
                ActionItemMetadata.objects.filter(
                    assignee_id=assignee, action_item_id=existing_ac
                ).delete()
            except Exception as e:
                logger.warning(
                    'Failed removing unassigned action item id'
                    f':{existing_ac} from assignee:'
                    f' {assignee}. Error {e}.'
                )


@transaction.atomic
def update_action_items(action_items_from_view, info):
    tmp_action_items_view = [ac.unique_action_item_id for ac in action_items_from_view]
    logger.info(
        'Action Items from view: '
        f'{tmp_action_items_view} for username {info.context.user}, '
        f'organization: {info.context.user.organization_id}'
    )

    updated_action_items_ids = []
    action_items_assigned_to_user = ActionItemMetadata.objects.filter(
        assignee=info.context.user
    )
    all_action_items_ids = [ac.action_item_id for ac in action_items_assigned_to_user]
    logger.info(
        'Action Items from ActionItemMetadata:'
        f' {all_action_items_ids} for username {info.context.user},'
        f'organization: {info.context.user.organization_id}'
    )

    for action_item in action_items_from_view:
        # For the task type quick_start. It doesn't need to create a
        # new object in ActionItemMetadata
        if action_item.type in NON_SUBTYPE_TASK_TYPES:
            continue
        updated_action_items_ids.append(action_item.unique_action_item_id)
        if ActionItemMetadata.objects.filter(
            action_item_id=action_item.unique_action_item_id, assignee=info.context.user
        ).exists():
            logger.info(
                f'Action item  {action_item.unique_action_item_id} '
                f'already exist for user {info.context.user}. '
                'Do not create item again'
            )
        else:
            try:
                obj, created = ActionItemMetadata.objects.get_or_create(
                    action_item_id=action_item.unique_action_item_id,
                    assignee=info.context.user,
                )
                logger.info(f'Action item {obj.action_item_id} created {created}')
            except Exception as e:
                logger.exception(
                    'Error Failed creating action item metadata id'
                    f':{action_item.unique_action_item_id} for assignee:'
                    f' {info.context.user}. Error '
                    f'{format_stack_in_one_line(e)}.'
                )
                continue

    # Updates the metadata items to remove from ActionItemMetadata the ones
    # that were unassigned from the given user
    remove_unassigned_action_items(
        all_action_items_ids, updated_action_items_ids, info.context.user
    )


def get_filtered_pending_data(filter_by, info):
    filter_query = get_filter_query(filter_by, info)

    return ActionItem.objects.filter(
        organization_id=info.context.user.organization_id,
        status__in=SUBTASKS_ACTION_ITEMS_STATUS,
    ).filter(filter_query)


class Mutation(graphene.ObjectType):
    update_dashboard_item = UpdateDashboardItem.Field()
    update_dashboard_action_item = UpdateDashboardActionItem.Field()


class Query(object):
    action_items = graphene.Field(
        ActionItemResponseType,
        order_by=graphene.Argument(OrderInputType, required=False),
        filter=graphene.JSONString(required=False),
        pagination=graphene.Argument(PaginationInputType, required=False),
        action_items_status=graphene.String(),
    )

    task_view_action_items = graphene.Field(
        TaskViewResponseType,
        filter=graphene.JSONString(required=False),
        action_items_status=graphene.String(),
    )

    pending_seen_items = graphene.Field(PendingItemsResponseType)

    calendar_due_tasks = graphene.Field(
        ActionItemListResponseType,
        filter=graphene.JSONString(required=False),
        action_items_status=graphene.String(),
    )

    calendar_action_badges = graphene.Field(
        CalendarActionItemResponseType, filter=graphene.JSONString(required=False)
    )

    quick_links = graphene.List(QuickLinkType)

    framework_cards = graphene.List(FrameworkCardType)

    @login_required
    @service_exception('Failed to retrieve dashboard action items')
    @permission_required('dashboard.view_dashboard')
    def resolve_action_items(self, info, **kwargs):
        organization = info.context.user.organization
        ac_status = kwargs.get('action_items_status')
        order_by = kwargs.get('order_by', {'field': 'due_date', 'order': 'ascend'})
        field = order_by.get('field')
        order = order_by.get('order')

        filter_by = kwargs.get('filter', {})
        filter_by['user'] = filter_by.get('user', True)
        filter_query = get_filter_query(filter_by, info)
        filter_query.add(Q(organization_id=organization.id), Q.AND)

        order_query = (
            F(field).desc(nulls_last=True)
            if order == 'descend'
            else F(field).asc(nulls_last=True)
        )

        status = SUBTASKS_ACTION_ITEMS_STATUS + ACTION_ITEM_INITIAL_STATUS

        status_query = (
            {'status__in': status}
            if ac_status == 'pending'
            else {'status': SUBTASK_COMPLETED_STATUS}
        )

        filter_query.add(Q(**status_query), Q.AND)

        data = ActionItem.objects.filter(filter_query).order_by(order_query)

        if ac_status == 'pending':
            update_action_items(data, info)

        pagination = kwargs.get('pagination')
        page = pagination.page if pagination else DEFAULT_PAGE
        page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE
        paginated_result = get_paginated_result(data, page_size, page)

        return ActionItemResponseType(
            data=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @laika_service(
        exception_msg='Failed to retrieve action items',
        permission='dashboard.view_dashboard',
    )
    def resolve_task_view_action_items(self, info, **kwargs):
        organization = info.context.user.organization
        status = kwargs.get('action_items_status')

        status_query = (
            {'status__in': ACTION_ITEM_INITIAL_STATUS}
            if status == ActionItemStatus.PENDING
            else {
                'status__in': [
                    ActionItemStatus.COMPLETED,
                    ActionItemStatus.NOT_APPLICABLE,
                ]
            }
        )

        filter_by = kwargs.get('filter', {})
        filter_query = get_filter_query(filter_by, info)
        filter_query.add(Q(**status_query), Q.AND)
        filter_query.add(Q(organization_id=organization.id), Q.AND)

        order_query = F('due_date').asc(nulls_last=True)

        action_items = TaskView.objects.filter(filter_query).order_by(order_query)

        if status == 'pending':
            update_action_items(action_items, info)

        return TaskViewResponseType(data=action_items)

    @login_required
    @service_exception('Failed to retrieve pending seen items')
    @permission_required('dashboard.view_dashboard')
    def resolve_pending_seen_items(self, info, **kwargs):
        data = ActionItem.objects.filter(
            organization_id=info.context.user.organization_id,
            status__in=SUBTASKS_ACTION_ITEMS_STATUS,
            assignee=info.context.user,
        )
        update_action_items(data, info)
        return PendingItemsResponseType(data=data)

    @login_required
    @service_exception('Failed to retrieve dashboard action items')
    @permission_required('dashboard.view_dashboard')
    def resolve_calendar_due_tasks(self, info, **kwargs):
        filter_by = kwargs.get('filter', {})
        data = get_filtered_pending_data(filter_by, info)
        return ActionItemListResponseType(data=data)

    @login_required
    @service_exception('Failed to retrieve calendar action badges')
    @permission_required('dashboard.view_dashboard')
    def resolve_calendar_action_badges(self, info, **kwargs):
        filter_by = kwargs.get('filter', {})
        data = get_filtered_pending_data(filter_by, info)
        items = [
            CalendarActionItemType(date=ai.due_date, has_items=True) for ai in data
        ]
        return CalendarActionItemResponseType(data=items)

    @laika_service(
        permission='dashboard.view_dashboard',
        exception_msg='Cannot get quick links cards data',
        revision_name='Quick Links data',
    )
    def resolve_quick_links(self, info, **kwargs):
        quick_links_list: List[QuickLinkBase] = [
            ControlQuickLink(),
            PolicyQuickLink(),
            MonitorQuickLink(),
            IntegrationQuickLink(),
        ]
        organization_id = info.context.user.organization_id

        quick_links = [
            quick_link.get_quick_link(organization_id)
            for quick_link in quick_links_list
        ]

        return quick_links

    @login_required
    @service_exception('Failed to retrieve available frameworks')
    @permission_required('dashboard.view_dashboard')
    def resolve_framework_cards(self, info):
        organization_id = info.context.user.organization_id

        unlocked_certifications = UnlockedOrganizationCertification.objects.filter(
            organization__id=organization_id
        ).prefetch_related(
            'certification__sections',
            Prefetch(
                'certification__sections__controls',
                queryset=Control.objects.filter(
                    organization_id=organization_id
                ).distinct(),
            ),
            'certification__sections__controls__action_items',
        )

        return [
            get_certification_card_payload(
                certification, organization_id=organization_id
            )
            for certification in unlocked_certifications
        ]

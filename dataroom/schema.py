import datetime
import logging

import graphene
from django.db.models import Q

from dataroom.constants import ARCHIVED, FILTER_STATUS
from dataroom.models import Dataroom, DaysOrderBy
from dataroom.mutations import (
    AddDataroomDocuments,
    CreateDataroom,
    DeleteDataroomDocuments,
    ToggleDataroom,
)
from dataroom.types import DataroomType, FilterGroupsDatarooms
from laika.auth import login_required, permission_required
from laika.backends.concierge_backend import ConciergeAuthenticationBackend
from laika.backends.laika_backend import AuthenticationBackend
from laika.decorators import service
from laika.utils.exceptions import ServiceException, service_exception
from user.constants import CONCIERGE, ROLE_SUPER_ADMIN

logger = logging.getLogger(__name__)


def create_filter_dataroom_data():
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
                {'id': ARCHIVED, 'name': 'Archived', 'subItems': [], 'disabled': False}
            ],
        },
    ]


def filter_datarooms(info, **kwargs):
    filter_by = kwargs.get('filter', {})
    user_role = info.context.user.role

    if user_role == CONCIERGE:
        organization_id = kwargs.get('organization_id')

        if not organization_id:
            raise ServiceException('Bad Request, some parameters are missed')

    else:
        organization_id = info.context.user.organization_id

    all_datarooms = Dataroom.objects.filter(organization_id=organization_id)
    if all_datarooms.count() == 0:
        return all_datarooms

    if not filter_by.items():
        all_datarooms = Dataroom.objects.filter(
            organization_id=organization_id, is_soft_deleted=False
        )

    filter_query = Q()
    for field, value in filter_by.items():
        _if_filter_by_days(filter_query, field, value)
        _if_filter_by_archived(filter_query, field, value)

    return all_datarooms.filter(filter_query)


def _if_filter_by_days(filter_query, field, value):
    if field == DaysOrderBy.FIELD.value:
        time_filter = next(
            (
                filter[1]
                for filter in DaysOrderBy.FILTERS.value
                if filter[0] == value.upper()
            ),
            None,
        )

        if field == DaysOrderBy.FIELD.value and time_filter:
            last_updated = Dataroom.objects.all().latest('updated_at')
            d = last_updated.updated_at - datetime.timedelta(days=time_filter)
            filter_query.add(Q(updated_at__gte=d), Q.AND)


def _if_filter_by_archived(filter_query, field, value):
    if field == FILTER_STATUS and value == ARCHIVED:
        filter_query.add(Q(is_soft_deleted=True), Q.AND)
    else:
        filter_query.add(Q(is_soft_deleted=False), Q.AND)


def filter_templates_query(user):
    is_super = user.role == ROLE_SUPER_ADMIN
    return {'is_template': False} if not is_super else {}


class Mutation(graphene.ObjectType):
    create_dataroom = CreateDataroom.Field()
    toggle_dataroom = ToggleDataroom.Field()
    add_files_to_dataroom = AddDataroomDocuments.Field()
    delete_dataroom_files = DeleteDataroomDocuments.Field()


class Query(object):
    dataroom = graphene.Field(DataroomType, id=graphene.Int(required=True))
    datarooms = graphene.List(
        DataroomType,
        filter=graphene.JSONString(required=False),
        organization_id=graphene.String(),
    )
    filter_groups_datarooms = graphene.List(FilterGroupsDatarooms, required=True)

    @login_required
    @service_exception('Cannot get dataroom details')
    @permission_required('dataroom.view_dataroom')
    def resolve_dataroom(self, info, **kwargs):
        return Dataroom.objects.get(
            id=kwargs.get('id'),
            organization=info.context.user.organization,
            is_soft_deleted=False,
        )

    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'dataroom.view_dataroom',
            },
        ],
        exception_msg='Failed to retrieve dataroom list',
    )
    def resolve_datarooms(self, info, **kwargs):
        return filter_datarooms(info, **kwargs)

    @login_required
    @service_exception('Cannot get filter groups')
    @permission_required('dataroom.view_dataroom')
    def resolve_filter_groups_datarooms(self, info, **kwargs):
        return create_filter_dataroom_data()

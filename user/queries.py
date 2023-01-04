import logging

from django.db.models import Case, CharField, F, Q, Value, When
from django.db.models.functions import Concat, Replace

from laika.constants import ATTRIBUTES_TYPE
from laika.utils.get_organization_by_user_type import get_organization_by_user_type
from laika.utils.objects import is_valid_model_field
from laika.utils.permissions import map_permissions
from laika.utils.query_builder import get_incredible_filter_query
from user.constants import USER_ATTRIBUTES, USER_ROLES
from user.models import (
    DISCOVERY_STATE_CONFIRMED,
    DISCOVERY_STATE_IGNORED,
    DISCOVERY_STATE_NEW,
    User,
)
from user.utils.user_model_query import find_user_by_id_type

logger = logging.getLogger('User')


def get_order_by(order_by):
    if order_by and order_by.get('field'):
        field = (
            'manager__first_name'
            if order_by.get('field') == 'manager'
            else order_by.get('field')
        )
        return (
            (F(field).desc(nulls_last=True),)
            if order_by.get('order') == 'descend'
            else (F(field).asc(nulls_first=True),)
        )
    else:
        return 'is_active', 'first_name'


def resolve_user_q(self, info, kwargs):
    email = kwargs.get('email')
    id = kwargs.get('id')
    if not email and not id:
        return None
    if id:
        return find_user_by_id_type(id, info)
    return User.objects.get(
        email=email, organization_id=info.context.user.organization_id
    )


def resolve_users_q(self, info, kwargs):
    emails = kwargs.get('emails')
    all_users = kwargs.get('all_users')
    filter_query = kwargs.get('filter', {})
    order_by = kwargs.get('order_by', {})
    exclude_roles = filter_query.get('exclude_roles', [])
    exclude_emails = filter_query.get('exclude_emails', [])
    roles_in = filter_query.get('roles_in', [])
    all_but_supers = kwargs.get('exclude_super_admin')
    exclude_super = emails is None and all_users is None
    filters = kwargs.get('filters')
    organization_id = kwargs.get('organization_id')
    show_deleted_users = kwargs.get('show_deleted_users')

    organization = get_organization_by_user_type(info.context.user, organization_id)

    filter_params = {'organization_id': organization.id, 'is_active': True}

    if all_users or all_but_supers:
        filter_params = {'organization_id': organization.id}

    if exclude_super:
        exclude_roles.append(USER_ROLES['SUPER_ADMIN'])

    if emails and len(emails) > 0:
        filter_params['email__in'] = emails

    if roles_in and len(roles_in) > 0:
        filter_params['role__in'] = roles_in

    filter_params['discovery_state'] = DISCOVERY_STATE_CONFIRMED

    users = User.all_objects if show_deleted_users else User.objects
    users = (
        users.annotate(
            name=Case(
                When(first_name__exact='', then=None),
                default='first_name',
                output_field=CharField(),
            )
        )
        .exclude(role__in=exclude_roles)
        .filter(**filter_params)
        .exclude(email__in=exclude_emails)
        .filter(**filter_params)
    )
    if filters:
        users = users.filter(build_user_incredible_filter(filters))
    # If the field is not an model's attribute the sorter will be in the FE
    if is_valid_model_field(User, order_by.get('field')):
        users = users.order_by(*get_order_by(order_by))
    permissions = map_permissions(info.context.user, 'user')

    return {'users': users, 'permissions': permissions}


def resolve_users_by_role_q(self, info, kwargs):
    filter_query = kwargs.get('filter', {})
    roles_in = filter_query.get('roles_in', [])
    order_by = kwargs.get('order_by', {})

    filter_params = {}

    if roles_in and len(roles_in) > 0:
        filter_params['role__in'] = roles_in

    filter_params['discovery_state'] = DISCOVERY_STATE_CONFIRMED
    users = (
        User.objects.annotate(
            name=Case(
                When(first_name__exact='', then=None),
                default='first_name',
                output_field=CharField(),
            )
        )
        .filter(**filter_params)
        .order_by(*get_order_by(order_by))
    )

    permissions = map_permissions(info.context.user, 'user')

    return {'users': users, 'permissions': permissions}


def resolve_discovered_people_q(self, info, kwargs):
    filter_params = {
        'organization_id': info.context.user.organization_id,
        'discovery_state__in': [DISCOVERY_STATE_NEW, DISCOVERY_STATE_IGNORED],
    }
    users = User.objects.filter(**filter_params)
    return {'users': users}


def resolve_search_users_q(self, info, kwargs):
    search_criteria = kwargs.get('search_criteria', '').replace(' ', '')
    filter_query = kwargs.get('filter', {})
    show_deleted_users = kwargs.get('show_deleted_users')

    organization = get_organization_by_user_type(
        info.context.user, kwargs.get('organization_id')
    )

    users = User.all_objects if show_deleted_users else User.objects
    users_match = (
        users.annotate(
            first_name_no_spaces=Replace('first_name', Value(' '), Value('')),
            last_name_no_spaces=Replace('last_name', Value(' '), Value('')),
            full_name=Concat('first_name_no_spaces', 'last_name_no_spaces'),
        )
        .filter(
            Q(organization_id=organization.id)
            & (
                Q(full_name__icontains=search_criteria)
                | Q(email__icontains=search_criteria)
            )
        )
        .exclude(role__in=filter_query.get('exclude_roles', []))
        .exclude(email__in=filter_query.get('exclude_emails', []))
    )

    return users_match


def format_value(value, attr_type):
    """
    Set the value up depending of the attribute type.
    """
    if attr_type in [ATTRIBUTES_TYPE['USER'], ATTRIBUTES_TYPE['SINGLE_SELECT']]:
        return value.split(',')

    if attr_type == ATTRIBUTES_TYPE['BOOLEAN']:
        if value == 'true':
            value = True
        elif value == 'false':
            value = False

    return value


def build_user_incredible_filter(filters):
    """
    Build Q object for each filter in the object.
    The attributes are defined by the user model and if one attribute is None
    it raises an Exception.
    """

    filter_query = Q()
    for filter in filters:
        field = filter['field']
        attr = USER_ATTRIBUTES.get(field)
        if attr is None:
            logger.exception(
                'Error calling build_user_incredible_filter function'
                f'stack: Unable to get attribute {attr} from field {field}'
            )
            raise Exception('The field does not exist in user model')
        incredible_filter = get_incredible_filter_query(
            field=attr['query_path'],
            value=format_value(filter['value'], attr['attribute_type']),
            operator=filter['operator'],
            attribute_type=attr['attribute_type'],
        )
        filter_query.add(incredible_filter, Q.AND)

    return filter_query

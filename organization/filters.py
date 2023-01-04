import datetime
import logging
import re

from dateutil.parser import parse
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from certification.models import Certification
from organization.constants import BOOLEAN, DATE, SINGLE_SELECT, USER
from organization.query_builder import OPERATORS
from user.models import User

logger = logging.getLogger('objects')


def get_filter_query(filters):
    filter_query = Q()

    for element in filters:
        field = element['field']
        value = element.get('value', '')
        operator = element['operator']
        column_type = element['type']

        field = re.sub(r'(?<!^)(?=[A-Z])', '_', field).lower()
        try:
            handler = OPERATORS[column_type][operator.upper()]
        except Exception:
            raise ValueError(f'Invalid Operator: "{operator}"')

        filter_format_params = {
            USER: format_email,
            DATE: format_date,
            BOOLEAN: format_boolean,
            SINGLE_SELECT: format_select_state,
        }

        if handler is not None:
            fn_format = filter_format_params.get(column_type, lambda x: x)
            field_filter_query = handler(field, fn_format(value), column_type)
            filter_query.add(field_filter_query, Q.AND)

    return filter_query


def format_boolean(value):
    return True if value == 'true' else False


def format_email(value):
    if not value:
        return None
    try:
        emails = [email.strip() for email in value.split(',')]

        users = User.objects.filter(email__in=emails)
        if not users.exists():
            raise ObjectDoesNotExist(f'Email(s): {emails}')

        # To upload specific cell value
        if users.count() == 1:
            return users.first().as_dict()

        # Users that were split from parameter value
        return [user.as_dict() for user in users]
    except ObjectDoesNotExist as e:
        logger.warning(
            'User not found for email "%s" in attribute "%s" '
            'and object type id "%s". Error: "%s"',
            value,
            e,
        )
        # To store in the json data the invalid email
        return {'email': value}


def format_date(value):
    if isinstance(value, datetime.datetime):
        return value.strftime('%Y-%m-%d')

    if isinstance(value, str):
        try:
            return parse(value)
        except ValueError:
            pass

    return None


def format_select_state(value):
    if not value:
        return None
    try:
        return [state for state in value.split(',')]
    except Exception as e:
        logger.warning(f'Error happened while filtering: {e}')
        return value


def roadmap_groups_per_framework_query(certification_id, filter_query):
    certification = Certification.objects.get(id=certification_id)
    filter_query.add(Q(reference_id__endswith=certification.code), Q.AND)


def roadmap_filter_query(filters):
    filter_query = Q()

    if not filters:
        return filter_query

    filter_to_query_mapping = {'framework': roadmap_groups_per_framework_query}

    for filter, value in filters.items():
        filter_to_query_mapping[filter](value, filter_query)

    return filter_query

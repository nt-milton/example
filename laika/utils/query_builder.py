import ast

from django.db.models import Q

from laika.constants import ATTRIBUTES_TYPE


def build_empty_query(field, value, negative_form):
    q = (
        Q(**{f'{field}': None})
        | Q(**{f'{field}': ''})
        | Q(**{f'{field}__isnull': True})
    )

    if negative_form:
        return ~q

    return q


def build_lookups_query(field, values, lookup='', negative_form=False):
    values = values if isinstance(values, list) else [values]
    q = ~Q() if negative_form else Q()

    for val in values:
        val = val.strip() if isinstance(val, str) else val
        filter_query = Q(**{f'{field}{lookup}': val})
        q.add(filter_query, Q.OR)

    return q


def is_empty(negative_form=False):
    def builder(field, value):
        return build_empty_query(field, value, negative_form)

    return builder


def operator(lookup='', negative_form=False):
    def builder(field, value):
        return build_lookups_query(field, value, lookup, negative_form)

    return builder


def has_any_of_operator():
    def builder(field, value):
        return build_lookups_query(field, value.split(','), '__iexact')

    return builder


def between_operator():
    def builder(field, value):
        date_range = value
        if isinstance(value, str):
            date_range = ast.literal_eval(value)
        return Q(**{f'{field}__range': date_range})

    return builder


def format_value(value, **kwargs):
    if isinstance(value, list):
        return value

    if kwargs.get('type', '') == 'BOOLEAN':
        return value in [True, 'true', 'True', 'TRUE', 't', 'T', 'yes', 'Yes', '1', 1]

    return str(value) if value is not None else None


def get_incredible_filter_query(field, value, operator, attribute_type):
    handler = None
    q_filter = None

    try:
        handler = OPERATORS[attribute_type][operator.upper()]
    except Exception:
        raise ValueError(f'Invalid Operator: "{operator}"')

    if handler is not None:
        ctx = {'format_for_filter': True, 'type': attribute_type}
        q_filter = handler(field, format_value(value, **ctx))
    return q_filter


EMPTY_OPERATORS = {
    'IS_EMPTY': is_empty(),
    'IS_NOT_EMPTY': is_empty(negative_form=True),
}


MULTIPLE_CHOICES_OPERATORS = {
    'IS_ANY_OF': operator(),
    'IS_NONE_OF': operator(negative_form=True),
}

COMPARISON_OPERATORS = {
    'LESS_THAN': operator('__lt'),
    'LESS_THAN_OR_EQUALS_TO': operator('__lte'),
    'GREATER_THAN': operator('__gt'),
    'GREATER_THAN_OR_EQUALS_TO': operator('__gte'),
    'IS_BETWEEN': between_operator(),
}


EQUAL = operator()
NOT_EQUAL = operator(negative_form=True)


OPERATORS = {
    ATTRIBUTES_TYPE['BOOLEAN']: {
        'IS': EQUAL,
    },
    ATTRIBUTES_TYPE['TEXT']: {
        'IS': operator('__iexact'),
        'CONTAINS': operator('__icontains'),
        'DOES_NOT_CONTAIN': operator('__icontains', negative_form=True),
        'HAS_ANY_OF': has_any_of_operator(),
        **EMPTY_OPERATORS,
    },
    ATTRIBUTES_TYPE['NUMBER']: {
        'EQUALS': EQUAL,
        'DOES_NOT_EQUAL': NOT_EQUAL,
        **COMPARISON_OPERATORS,
        **EMPTY_OPERATORS,
    },
    ATTRIBUTES_TYPE['DATE']: {'IS': EQUAL, **COMPARISON_OPERATORS, **EMPTY_OPERATORS},
    ATTRIBUTES_TYPE['USER']: {
        'IS': EQUAL,
        'IS_NOT': NOT_EQUAL,
        **MULTIPLE_CHOICES_OPERATORS,
        **EMPTY_OPERATORS,
    },
    ATTRIBUTES_TYPE['SINGLE_SELECT']: {
        'IS': operator('__iexact'),
        'IS_NOT': operator('__iexact', negative_form=True),
        **MULTIPLE_CHOICES_OPERATORS,
        **EMPTY_OPERATORS,
    },
    ATTRIBUTES_TYPE['JSON']: {**EMPTY_OPERATORS},
}

from django.db.models import Q

from organization.constants import BOOLEAN, DATE, SINGLE_SELECT, TEXT, USER

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 50


def build_empty_query(field, value, column_type, negative_form):
    if column_type == USER:
        q = Q(**{f'{field}': None}) | Q(**{f'{field}': '0'})
    elif column_type == DATE:
        q = Q(**{f'{field}': None}) | Q(**{f'{field}__date': '1800-01-01'})
    else:
        q = Q(**{f'{field}': None}) | Q(**{f'{field}': ''})

    if negative_form:
        return ~q

    return q


def build_lookups_query(
    field, values, column_type, lookup='', negative_form=False, multiple_values=False
):
    values = values if isinstance(values, list) else [values]
    q = ~Q() if negative_form else Q()
    amount_values = len(values)

    for val in values:
        if column_type == USER:
            if val is not None and (
                amount_values == 1 or negative_form or multiple_values
            ):
                filter_query = Q(**{f'{field}{lookup}': val['id']})
            elif not multiple_values:
                filter_query = Q(**{f'{field}{lookup}': '-1'})
            else:
                return ~q
        elif column_type == DATE:
            filter_query = Q(**{f'{field}__date{lookup}': val})
        else:
            filter_query = Q(**{f'{field}{lookup}': val})

        q.add(filter_query, Q.OR)

    return q


def is_empty(negative_form=False):
    def builder(field, value, column_type):
        return build_empty_query(field, value, column_type, negative_form)

    return builder


def operator(lookup='', negative_form=False, multiple_values=False):
    def builder(field, value, column_type):
        return build_lookups_query(
            field, value, column_type, lookup, negative_form, multiple_values
        )

    return builder


MULTIPLE_CHOICES_OPERATORS = {
    'IS_ANY_OF': operator(multiple_values=True),
    'IS_NONE_OF': operator(negative_form=True, multiple_values=True),
}

EMPTY_OPERATORS = {
    'IS_EMPTY': is_empty(),
    'IS_NOT_EMPTY': is_empty(negative_form=True),
}

COMPARISION_OPERATORS = {
    'LESS_THAN': operator('__lt'),
    'LESS_THAN_OR_EQUALS_TO': operator('__lte'),
    'GREATER_THAN': operator('__gt'),
    'GREATER_THAN_OR_EQUALS_TO': operator('__gte'),
}


EQUAL = operator()
NOT_EQUAL = operator(negative_form=True)


OPERATORS = {
    TEXT: {
        'IS': operator('__iexact'),
        'CONTAINS': operator('__icontains'),
        'DOES_NOT_CONTAIN': operator('__icontains', negative_form=True),
        **EMPTY_OPERATORS,
    },
    DATE: {'IS': EQUAL, **COMPARISION_OPERATORS, **EMPTY_OPERATORS},
    USER: {
        'IS': EQUAL,
        'IS_NOT': NOT_EQUAL,
        **MULTIPLE_CHOICES_OPERATORS,
        **EMPTY_OPERATORS,
    },
    BOOLEAN: {
        'IS': EQUAL,
    },
    SINGLE_SELECT: {
        'IS': operator('__iexact'),
        'IS_NOT': operator('__iexact', negative_form=True),
        **MULTIPLE_CHOICES_OPERATORS,
        **EMPTY_OPERATORS,
    },
}

import pytest

from laika.utils.query_builder import (
    between_operator,
    build_lookups_query,
    format_value,
    has_any_of_operator,
)


@pytest.mark.functional
@pytest.mark.parametrize(
    'value, type, expected',
    [
        ([], '', []),
        (True, 'BOOLEAN', True),
        ('True', 'BOOLEAN', True),
        ('true', 'BOOLEAN', True),
        ('TRUE', 'BOOLEAN', True),
        ('T', 'BOOLEAN', True),
        ('t', 'BOOLEAN', True),
        ('1', 'BOOLEAN', True),
        ('Yes', 'BOOLEAN', True),
        ('yes', 'BOOLEAN', True),
        ('False', 'BOOLEAN', False),
        ('n', 'BOOLEAN', False),
        (False, 'BOOLEAN', False),
        ('Hello', 'TEXT', 'Hello'),
        (None, '', None),
    ],
)
def test_format_value(value, type, expected):
    kwargs = {'type': type}
    formatted_value = format_value(value, **kwargs)
    assert formatted_value == expected


@pytest.mark.functional
@pytest.mark.parametrize(
    'value', ["['01/01/2022', '05/05/2022']", ['01/01/2022', '05/05/2022']]
)
def test_between_operator(value):
    field = 'Created At'
    handler = between_operator()
    query = handler(field, value)
    assert str(query) == f"(AND: ('{field}__range', ['01/01/2022', '05/05/2022']))"


@pytest.mark.functional
def test_has_any_of_operator():
    field = 'Name'
    value = 'John,Julia, Robert'
    handler = has_any_of_operator()
    query = handler(field, value)
    assert (
        str(query)
        == "(OR: (AND: ), (AND: ('Name__iexact', 'John')), ('Name__iexact', 'Julia'),"
        " ('Name__iexact', 'Robert'))"
    )


@pytest.mark.functional
def test_build_lookups_query_array_values():
    field = 'Name'
    values = ['Jonathan', ' Joseph', 'Jotaro ', ' Jolene ']
    query = build_lookups_query(field, values)
    assert (
        str(query)
        == "(OR: (AND: ), (AND: ('Name', 'Jonathan')), ('Name', 'Joseph'), ('Name',"
        " 'Jotaro'), ('Name', 'Jolene'))"
    )


@pytest.mark.functional
def test_build_lookups_query_single_value():
    field = 'Name'
    values = 'SpeedWagon'
    query = build_lookups_query(field, values)
    assert str(query) == "(OR: (AND: ), (AND: ('Name', 'SpeedWagon')))"

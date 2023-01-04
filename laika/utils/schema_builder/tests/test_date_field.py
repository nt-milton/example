from datetime import datetime

import pytest

from laika.utils.schema_builder.types.date_field import DateFieldType


@pytest.mark.parametrize(
    'value, expected',
    [
        (datetime(2001, 12, 12), '2001-12-12'),
        ('12/12/2001', None),
        (None, None),
        (2, None),
        ('This is not a date', None),
    ],
)
def test_format_values(value, expected):
    date_field = DateFieldType(name='test', required=True)

    assert date_field.format(value) == expected


@pytest.mark.parametrize('value', ['12/12/2001', None, 2, []])
def test_validate_should_raise_an_error(value):
    date_field = DateFieldType(name='test', required=True)
    error = date_field.validate(value)
    assert error is not None


def test_validate_should_be_valid():
    date_field = DateFieldType(name='test', required=True)
    error = date_field.validate(datetime.now())
    assert error is None


def test_validate_not_required_field():
    date_field = DateFieldType(name='test', required=False)
    error = date_field.validate(None)
    assert error is None


def test_get_min_width():
    date_field = DateFieldType(name='test', required=True)
    width = date_field.get_min_width()
    assert width == 175


def test_get_export_header():
    date_field = DateFieldType(name='test', required=True)
    header = date_field.get_export_header()
    assert header == f'{date_field.name} (MM/DD/YYYY)'

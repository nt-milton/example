import pytest

from laika.utils.schema_builder.types.boolean_field import BooleanFieldType


@pytest.mark.parametrize(
    'value, expected',
    [
        (None, None),
        ('No', False),
        ('Yes', True),
        (True, True),
        (False, False),
    ],
)
def test_format(value, expected):
    boolean_field = BooleanFieldType(name='test', required=True)
    assert boolean_field.format(value) == expected


def test_validate():
    boolean_field = BooleanFieldType(name='test', required=True)
    error = boolean_field.validate('Yes')
    assert error is None


def test_validate_invalid_value():
    boolean_field = BooleanFieldType(name='test', required=True)
    error = boolean_field.validate('Maybe')
    assert error is not None


def test_validate_not_required_field():
    boolean_field = BooleanFieldType(name='test', required=False)
    error = boolean_field.validate(None)
    assert error is None


def test_validate_required_field():
    boolean_field = BooleanFieldType(name='test', required=True)
    error = boolean_field.validate(None)
    assert error is not None


def test_get_export_header():
    boolean_field = BooleanFieldType(name='test', required=True)
    header = boolean_field.get_export_header()
    assert header == f'{boolean_field.name} (Yes/No)'


def test_get_export_header_with_custom_values():
    boolean_field = BooleanFieldType(
        name='test', required=True, truthy_value='True', falsy_value='False'
    )
    header = boolean_field.get_export_header()
    assert header == f'{boolean_field.name} (True/False)'


@pytest.mark.parametrize(
    'value, expected',
    [
        (None, None),
        ('False', False),
        ('True', True),
        (True, True),
        (False, False),
    ],
)
def test_format_with_custom_values(value, expected):
    boolean_field = BooleanFieldType(
        name='test', required=True, truthy_value='True', falsy_value='False'
    )
    assert boolean_field.format(value) == expected

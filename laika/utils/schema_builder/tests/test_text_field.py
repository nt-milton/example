import pytest

from laika.utils.schema_builder.types.text_field import TextFieldType


def test_format_none_value():
    text_field = TextFieldType(name='test', required=True)

    assert text_field.format(None) is None


@pytest.mark.parametrize(
    'value, expected', [(0, '0'), (True, 'True'), ([], '[]'), ('Hello', 'Hello')]
)
def test_format_values(value, expected):
    text_field = TextFieldType(name='test', required=True)

    assert text_field.format(value) == expected


def test_validate_should_raise_an_error():
    text_field = TextFieldType(name='test', required=True)
    error = text_field.validate([])
    assert error is not None


def test_validate_should_be_valid():
    text_field = TextFieldType(name='test', required=True)
    text_field.validate('Hello')

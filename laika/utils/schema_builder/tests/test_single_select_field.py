import pytest

from laika.utils.schema_builder.types.single_select_field import SingleSelectField


@pytest.mark.parametrize(
    'value, expected',
    [
        (None, None),
        ('Non existing', None),
        ('Yes', 'Yes'),
    ],
)
def test_format_values(value, expected):
    single_select = SingleSelectField(name='test', required=True, options=['Yes', 'No'])
    assert single_select.format(value) == expected


@pytest.mark.parametrize(
    'value, expected',
    [
        (None, []),
        ('Non existing', []),
        ('Yes', ['Yes']),
        ('Yes,No', ['Yes', 'No']),
        ('Yes,No,Maybe', ['Yes', 'No']),
    ],
)
def test_format_for_filter(value, expected):
    single_select = SingleSelectField(name='test', required=True, options=['Yes', 'No'])
    assert single_select.format_for_filter(value) == expected


def test_validate_existing_field():
    single_select = SingleSelectField(name='test', required=True, options=['Yes', 'No'])
    single_select.validate('Yes')


def test_validate_non_existing_field():
    single_select = SingleSelectField(name='test', required=True, options=['Yes', 'No'])
    error = single_select.validate('Maybe')
    assert error.type == 'invalid_format'


def test_validate_required_field():
    single_select = SingleSelectField(name='test', required=True, options=['Yes', 'No'])
    error = single_select.validate(None)
    assert error.type == 'required_value'

import pytest

from laika.utils.schema_builder.types.email_field import EmailFieldType


@pytest.mark.parametrize(
    'value, expected',
    [
        (None, None),
        ('test@test.com', 'test@test.com'),
        ('test@heylaika.com', 'test@heylaika.com'),
        ('test@heylaika.net', 'test@heylaika.net'),
        ('test123@heylaika.com', 'test123@heylaika.com'),
        ('test_123@heylaika.com', 'test_123@heylaika.com'),
        ('test.testing@heylaika.com', 'test.testing@heylaika.com'),
        ('test@tester.testing', 'test@tester.testing'),
        (
            'test+testorganization+tester@heylaika.com',
            'test+testorganization+tester@heylaika.com',
        ),
        ('tester@test-testing.com', 'tester@test-testing.com'),
    ],
)
def test_format_values(value, expected):
    email_field = EmailFieldType(name='test', required=True)

    assert email_field.format(value) == expected


@pytest.mark.parametrize(
    'value',
    [
        None,
        'notemail.com',
        'notanemail@heylaika..com',
        'test()test@heylaika.this',
        'test...test@heylaika.this',
    ],
)
def test_validate_should_fail(value):
    email_field = EmailFieldType(name='test', required=True)
    error = email_field.validate(value)
    assert error is not None


@pytest.mark.parametrize(
    'value',
    [
        'test@heylaika.com',
        'test@heylaika.net',
        'test123@heylaika.com',
        'test_123@heylaika.com',
        'test.testing@heylaika.com',
        'test@tester.testing',
        'test+testorganization+tester@heylaika.com',
        'tester@test-testing.com',
    ],
)
def test_validate(value):
    email_field = EmailFieldType(name='test', required=True)
    error = email_field.validate(value)
    assert error is None


def test_validate_not_required_field():
    email_field = EmailFieldType(name='test', required=False)
    error = email_field.validate(None)
    assert error is None


def test_get_min_width():
    email_field = EmailFieldType(name='test', required=True)
    width = email_field.get_min_width()
    assert width == 200

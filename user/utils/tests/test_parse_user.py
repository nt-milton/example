import pytest

from user.utils.parse_user import parse_user_from_excel, sanitize_dict

user_dict = {
    'Email': 'john@doe.com',
    'First Name': ' John',
    'Last Name': ' Doe',
    'Role': 'OrganizationAdmin',
}


@pytest.mark.parametrize(
    'field_key, expected, received',
    [
        ('field', {'field': 'test value'}, {'field': 'test value '}),
        ('field', {'field': 'test value'}, {'field': '  test value'}),
        ('field', {'field': 'test value'}, {'field': '  test value '}),
    ],
)
def test_sanitize_dict(field_key, expected, received):
    actual = sanitize_dict(received)
    assert actual[field_key] == expected[field_key]


@pytest.mark.functional()
def test_parse_user_from_excel(graphql_organization):
    result = parse_user_from_excel(user_dict, graphql_organization)

    assert 'john@doe.com' == result['email']
    assert 'John' == result['first_name']
    assert 'Doe' == result['last_name']
    assert 'OrganizationAdmin' == result['role']
    assert graphql_organization.id == result['organization_id']
    assert not result['manager_email']


@pytest.mark.functional()
def test_parse_user_from_excel_manager(graphql_organization):
    user = user_dict.copy()
    user['Manager Email'] = 'ROSE@doe.com'

    result = parse_user_from_excel(user, graphql_organization)

    assert 'rose@doe.com' == result['manager_email']


@pytest.mark.functional()
def test_parse_user_from_excel_employment(graphql_organization):
    user = user_dict.copy()
    user['Employment Type'] = 'Contractor'
    user['Employment Subtype'] = 'Full-time'
    user['Background Check Status'] = 'N/A'

    result = parse_user_from_excel(user, graphql_organization)

    assert 'contractor' == result['employment_type']
    assert 'full_time' == result['employment_subtype']
    assert 'na' == result['background_check_status']


@pytest.mark.functional()
def test_parse_user_from_excel_with_number(graphql_organization):
    user = user_dict.copy()
    user['Phone Number'] = 123

    result = parse_user_from_excel(user, graphql_organization)

    assert 123 == result['phone_number']

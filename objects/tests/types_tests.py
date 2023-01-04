import pytest

from objects.tests.factory import (
    create_attribute,
    create_laika_object,
    create_object_type,
)
from objects.types import Types, UserAttributeType
from organization.tests import create_organization
from user.tests import create_user

TEST_EMAIL = 'test@heylaika.com'
TEST_EMAILS = 'test@heylaika.com,test2@heylaika.com'


@pytest.fixture()
def organization():
    return create_organization(flags=[], name='org-test')


@pytest.fixture()
def user(organization):
    return create_user(
        organization=organization,
        email=TEST_EMAIL,
        first_name='laika_fn',
        last_name='laika_ln',
        username='laika_un',
    )


@pytest.fixture()
def user_two(organization):
    return create_user(
        organization=organization,
        email='test2@heylaika.com',
        first_name='laika_fn2',
        last_name='laika_ln2',
        username='laika_un2',
    )


@pytest.fixture()
def object_type(organization):
    return create_object_type(
        organization=organization,
        display_name='Infrastructure Asset',
        type_name='infrastructure_asset',
        color='accentRed',
        display_index=5,
    )


@pytest.fixture()
def attribute(organization, object_type):
    return create_attribute(
        object_type=object_type,
        name='Field',
        attribute_type=Types.USER.name,
        sort_index=5,
        metadata={"is_protected": True},
    )


@pytest.mark.django_db
def test_success_format_with_one_email(organization, user, object_type, attribute):
    attribute_type = UserAttributeType(attribute)
    formatted = attribute_type.get_formatted_value(TEST_EMAIL)
    assert formatted == {
        'id': 1,
        'username': 'laika_un',
        'lastName': 'laika_ln',
        'firstName': 'laika_fn',
        'email': TEST_EMAIL,
    }


@pytest.mark.django_db
def test_success_format_with_two_emails(
    organization, user, user_two, object_type, attribute
):
    attribute_type = UserAttributeType(attribute)
    formatted = attribute_type.get_formatted_value(TEST_EMAILS)
    assert formatted != [
        {
            'id': 2,
            'username': 'laika_un2',
            'lastName': 'laika_ln2',
            'firstName': 'laika_fn2',
            'email': 'test2@heylaika.com',
        },
        {
            'id': 1,
            'username': 'laika_un',
            'lastName': 'laika_ln',
            'firstName': 'laika_fn',
            'email': 'test@heylaika.com',
        },
    ]


@pytest.mark.django_db
def test_format_with_invalid_email(organization, user, object_type, attribute):
    attribute_type = UserAttributeType(attribute)
    formatted = attribute_type.get_formatted_value('notexist@heylaika.com')
    assert formatted == {'email': 'notexist@heylaika.com'}


@pytest.mark.django_db
def test_lo_user_format_not_found(object_type, attribute):
    email = 'random@email.com'
    data = {attribute.name: email}
    lo = create_laika_object(object_type, None, data)
    assert lo.data[attribute.name]['email'] == email
    assert lo.data[attribute.name].keys() == {'email'}


@pytest.mark.django_db
def test_lo_user_format_found(user, object_type, attribute):
    data = {attribute.name: user.email}
    lo = create_laika_object(object_type, None, data)
    assert lo.data[attribute.name]['email'] == user.email
    assert lo.data[attribute.name]['id'] == user.id


@pytest.mark.django_db
def test_lo_user_format_found_two(user, user_two, object_type, attribute):
    data = {attribute.name: f'{user.email}, {user_two.email}'}
    lo = create_laika_object(object_type, None, data)
    assert lo.data[attribute.name]['email'] == user.email
    assert lo.data[attribute.name]['id'] == user.id

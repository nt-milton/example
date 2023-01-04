import pytest

from control.models import Control
from control.utils.filter_builder import FilterBuilder
from user.models import User


@pytest.fixture(name="_users")
def fixture_users(graphql_organization):
    user_1 = User.objects.create(
        organization=graphql_organization,
        email='user1@heylaika.com',
        first_name='user1',
        last_name='user1',
    )
    user_2 = User.objects.create(
        organization=graphql_organization,
        email='user2@heylaika.com',
        first_name='user2',
        last_name='user2',
    )
    return user_1, user_2


@pytest.fixture(name="_control1")
def fixture_controls(graphql_organization, _users):
    return Control.objects.create(
        organization=graphql_organization,
        name='Control test 1',
        implementation_notes='Implementation notes test',
    )


@pytest.mark.django_db
def test_resolve_controls_filters_owner(_users, _control1):
    _control1
    user_1, user_2 = _users

    _control1.owner1 = user_1
    _control1.owner2 = user_2
    _control1.save()

    builder = FilterBuilder()
    builder.add_owners(_control1.organization_id)
    filters_list = builder.export()

    expected = [
        {'id': 1, 'name': 'User1 User1', 'firstName': 'User1', 'lastName': 'User1'},
        {'id': 2, 'name': 'User2 User2', 'firstName': 'User2', 'lastName': 'User2'},
    ]

    actual = filters_list[0].get('items')

    assert expected == actual

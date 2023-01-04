import pytest

from user.constants import ROLE_MEMBER
from user.launchpad import launchpad_mapper
from user.models import DISCOVERY_STATE_NEW, User
from user.tests.factory import create_candidate_user, create_user


@pytest.mark.django_db
def test_user_launchpad_mapper(graphql_organization):
    user = create_user(
        graphql_organization,
        email='member1@heylaika.com',
        role=ROLE_MEMBER,
        first_name='Member1',
        last_name='Member1',
        username='member1',
        is_active=True,
    )
    create_candidate_user(
        graphql_organization,
        email='candidate1@heylaika.com',
        role=ROLE_MEMBER,
        first_name='Candidate1',
        last_name='Candidate1',
        discovery_state=DISCOVERY_STATE_NEW,
        is_active=False,
    )
    create_candidate_user(
        graphql_organization,
        email='candidate2@heylaika.com',
        role=ROLE_MEMBER,
        first_name='Candidate2',
        last_name='Candidate2',
        username='',
        discovery_state=DISCOVERY_STATE_NEW,
        is_active=False,
    )

    users = launchpad_mapper(User, graphql_organization.id)

    assert len(users) == 1
    assert users[0].id == user.id
    assert users[0].username == 'member1'
    assert users[0].name == 'Member1 Member1'
    assert users[0].email == 'member1@heylaika.com'
    assert users[0].url == '/people?userId=member1'

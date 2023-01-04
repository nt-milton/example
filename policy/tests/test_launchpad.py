import pytest

from policy.models import Policy
from policy.utils import launchpad

from .factory import create_empty_policy


@pytest.fixture
def policy(graphql_organization, graphql_user):
    return create_empty_policy(organization=graphql_organization, user=graphql_user)


@pytest.mark.django_db
def test_policy_mapper(policy, graphql_organization):
    policies = launchpad.launchpad_mapper(Policy, graphql_organization.id)

    assert len(policies) == 1
    assert policies[0].id == policy.id
    assert policies[0].display_id == f'P-{policy.display_id}'
    assert policies[0].description == policy.description
    assert policies[0].name == policy.name
    assert policies[0].url == f"/policies/{policy.id}"
    assert policies[0].text == policy.policy_text

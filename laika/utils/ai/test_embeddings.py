import pytest

from laika.utils.ai.constants import OPEN_AI_FLAG
from laika.utils.ai.embeddings import generate_policy_embedding
from organization.models import Organization
from organization.tests import create_organization
from policy.models import Policy, PublishedPolicy
from policy.tests.factory import create_published_empty_policy
from user.models import User

POLICY_TEXT = 'This is a policy text example'


@pytest.fixture
def organization_with_open_ai_flag_on() -> Organization:
    return create_organization(flags=[OPEN_AI_FLAG], name='Open AI Org')


@pytest.fixture
def published_policy(
    organization_with_open_ai_flag_on: Organization, graphql_user: User
):
    policy = create_published_empty_policy(
        organization=organization_with_open_ai_flag_on, user=graphql_user
    )
    policy.is_published = True
    policy.policy_text = POLICY_TEXT
    policy.save()
    return policy


@pytest.fixture
def not_published_policy(
    organization_with_open_ai_flag_on: Organization, graphql_user: User
):
    policy = create_published_empty_policy(
        organization=organization_with_open_ai_flag_on, user=graphql_user
    )
    policy.policy_text = POLICY_TEXT
    policy.save()
    return policy


@pytest.fixture
def published_policy_organization_no_flag(
    graphql_organization: Organization, graphql_user: User
):
    policy = create_published_empty_policy(
        organization=graphql_organization, user=graphql_user
    )
    policy.is_published = True
    policy.policy_text = POLICY_TEXT
    policy.save()
    return policy


@pytest.mark.functional
def test_generate_policy_embeddings(published_policy: Policy):
    generate_policy_embedding(published_policy)
    policy_with_embeddings = PublishedPolicy.objects.get(policy__id=published_policy.id)
    assert policy_with_embeddings.embedding.name.__contains__('embedding.csv')


@pytest.mark.functional
def test_generate_policy_embeddings_organization_with_no_flag(
    published_policy_organization_no_flag: Policy,
):
    generate_policy_embedding(published_policy_organization_no_flag)
    policy_without_embeddings = PublishedPolicy.objects.get(
        policy__id=published_policy_organization_no_flag.id
    )
    assert policy_without_embeddings.embedding.name == ''


@pytest.mark.functional
def test_generate_policy_embeddings_not_published(not_published_policy: Policy):
    generate_policy_embedding(not_published_policy)
    policy_without_embeddings = PublishedPolicy.objects.get(
        policy__id=not_published_policy.id
    )
    assert policy_without_embeddings.embedding.name == ''

import pytest

from library.search_factory import serialize_search_result
from library.tests.factory import create_library_entry, create_question
from organization.models import Organization
from policy.tests.factory import create_published_empty_policy
from user.tests import create_user


@pytest.mark.functional(permissions=['library.view_questionnaire'])
@pytest.mark.parametrize('search_type', ['question', 'library_entry'])
def test_serialize_library_results(graphql_organization: Organization, search_type):
    question = create_question(graphql_organization)

    results = {
        'question': [question],
        'library_entry': [question.library_entry],
    }

    result = serialize_search_result(results.get(search_type), search_type, 'Test')[0]

    assert result.get('id') == question.id


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_serialize_orphan_library_entry(graphql_organization: Organization):
    entry = create_library_entry(graphql_organization)

    result = serialize_search_result([entry], 'library_entry', 'Test')

    assert len(result) == 0


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_serialize_policy(graphql_organization: Organization):
    user = create_user(graphql_organization)
    policy = create_published_empty_policy(graphql_organization, user)
    policy_uuid = policy.id

    result = serialize_search_result([policy], 'policy', 'Test')

    assert len(result) == 1
    assert result[0]['id'] == policy_uuid

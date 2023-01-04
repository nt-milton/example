from unittest.mock import patch

import pytest

from organization.models import Organization
from policy.models import Policy
from program.models import Task
from search import search
from search.search import _policy_hits, _question_hits
from user.models import User


@pytest.fixture
def user():
    return User(organization=Organization())


@pytest.fixture
def policy(graphql_organization):
    return Policy(
        name='Dummy Policy',
        organization=graphql_organization,
        is_published=True,
        policy_text='my policy search test',
    )


@patch('concurrent.futures.ThreadPoolExecutor.map')
def test_global_search_with_results(pool_map, user):
    expected_results = ['test search']
    pool_map.return_value = [expected_results]

    input_list = ['test', 'doc-test.ext', 'doc_test', 'doc_test.ext']
    for text in input_list:
        response = search.global_search(user, text, [])
        assert pool_map.called
        assert response == expected_results


@patch('concurrent.futures.ThreadPoolExecutor.map')
def test_global_search_failed_sum(pool_map, user):
    invalid_response = 0
    pool_map.return_value = invalid_response

    response = search.global_search(user, 'test', [])
    assert pool_map.called
    assert response == []


@patch('concurrent.futures.ThreadPoolExecutor.map')
def test_search_with_timeout(pool_map, user):
    from concurrent import futures

    pool_map.side_effect = futures._base.TimeoutError()

    response = search.global_search(user, 'test', [])
    assert pool_map.called
    assert response == []


@patch('concurrent.futures.ThreadPoolExecutor.map')
def test_search_with_exception(pool_map, user, capsys):
    search.logger.exception = print
    criteria = 'test'
    pool_map.side_effect = ValueError('Dummy error')

    response = search.global_search(user, criteria, [])

    out, _ = capsys.readouterr()
    assert pool_map.called
    assert response == []
    assert f'Error found with criteria: {criteria}' in out


@patch('concurrent.futures.ThreadPoolExecutor.map')
def test_search_with_special_characters(pool_map, user):
    input_list = ['$test^', 'untli^', 'sea%rching']
    for text in input_list:
        response = search.global_search(user, text, [])
        assert not pool_map.called
        assert response == []


@pytest.fixture
def task(user):
    return Task(name='Task 1')


@patch('concurrent.futures.ThreadPoolExecutor.map')
def test_global_search_when_playbooks_is_off(pool_map, user, task):
    expected_results = []
    response = search.global_search(user, 'Task 1', ['task'])
    assert pool_map.called
    assert response == expected_results


@pytest.mark.django_db
@patch('concurrent.futures.ThreadPoolExecutor.map')
def test_global_search_for_policy(pool_map, user, policy):
    expected_results = ['Dummy Policy']
    pool_map.return_value = [expected_results]

    response = search.global_search(user, 'my policy', [])
    assert pool_map.called
    assert response == expected_results


@pytest.mark.django_db
def test_policy_hits(policy):
    policy.save()
    hits = {'policy': [str(policy.id)]}
    result = _policy_hits(str(policy.organization_id), hits)

    assert result['policy'][str(policy.id)] == policy


@pytest.mark.django_db
def test_question_hits_should_return_default_question(question):
    hits = {'question': [str(question.id)]}
    result = _question_hits(str(question.library_entry.organization_id), hits)

    assert result['question'][str(question.id)] == question


@pytest.mark.django_db
def test_question_hits_should_return_default_question_for_equivalent_question(
    question, default_question
):
    question.default = False
    question.save()
    default_question.equivalent_questions.add(question)

    hits = {'question': [str(question.id)]}
    result = _question_hits(str(question.library_entry.organization_id), hits)

    assert result['question'][str(question.id)] == default_question

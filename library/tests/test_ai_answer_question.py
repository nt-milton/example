from unittest.mock import patch

import pytest

from laika.utils.dictionaries import DictToClass
from library.ai_answer_question import (
    answer_question_from_policy,
    can_use_answer,
    construct_question_prompt,
    get_best_policy_option,
    get_embedding,
    use_ai_answer,
)
from library.constants import RESULT_FOUND
from library.models import Question
from policy.tests.factory import create_published_empty_policy


@pytest.mark.functional
def test_construct_question_prompt_should_add_texts(default_question: Question):
    prompt = construct_question_prompt(
        default_question,
        {'embedding_index': 0, 'texts': ["Hello", "World", "from", "an", "example"]},
    )
    assert "Hello World from an example" in prompt


@pytest.mark.functional
def test_construct_question_prompt_should_add_unknown(default_question: Question):
    prompt = construct_question_prompt(
        default_question, {'embedding_index': 0, 'texts': ["Hello"]}
    )
    assert '"unknown"' in prompt


@pytest.mark.parametrize(
    ('answer', 'expected'),
    [
        ('my answer', True),
        ('unknown', False),
        ('Unknown', False),
    ],
)
def test_can_use_answer(answer, expected):
    result = can_use_answer(answer)
    assert result == expected


@pytest.mark.functional
def test_use_ai_answer(default_question: Question):
    ai_answer = 'my ai answer'
    use_ai_answer(default_question, ai_answer)

    assert default_question.fetch_status == RESULT_FOUND
    assert default_question.library_entry.answer_text == ai_answer


@patch('openai.Embedding.create')
def test_get_embedding(create):
    create.return_value = {'data': [{'embedding': 'embeddingValue'}]}
    embedding = get_embedding('hello', 'custom-model')

    assert embedding == 'embeddingValue'
    create.assert_called_with(input='hello', model='custom-model')


@pytest.mark.functional
@patch('openai.Completion.create')
def test_answer_question_from_policy_with_valid_answer(
    create, default_question: Question
):
    create.return_value = DictToClass(
        {'choices': [DictToClass({'text': '\nnew answer\n'})]}
    )
    answered = answer_question_from_policy(
        default_question,
        {
            'embedding_index': 3,
            'texts': [
                "Hello",
                "world",
                "from",
                "another",
                "country",
                "with",
                "awesome",
                "people",
            ],
        },
    )

    assert answered
    assert default_question.library_entry.answer_text == 'new answer'


@pytest.mark.functional
@patch('openai.Completion.create')
def test_answer_question_from_policy_with_invalid_answer(
    create, default_question: Question
):
    old_answer = default_question.library_entry.answer_text
    create.return_value = DictToClass(
        {'choices': [DictToClass({'text': '\nUNKNOWN\n'})]}
    )
    answered = answer_question_from_policy(
        default_question, {'embedding_index': 0, 'texts': ["Hello"]}
    )

    assert not answered
    assert default_question.library_entry.answer_text == old_answer


@pytest.mark.functional
def test_get_best_policy_option_should_return_none(graphql_organization, graphql_user):
    create_published_empty_policy(organization=graphql_organization, user=graphql_user)

    best_option = get_best_policy_option(graphql_organization, [])

    assert best_option is None

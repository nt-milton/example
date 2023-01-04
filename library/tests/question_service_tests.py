import random
from contextlib import contextmanager
from datetime import datetime
from typing import List, Tuple
from unittest.mock import patch

import django.utils.timezone as timezone
import pytest
from django.db.models import Case, FloatField, Value, When

from laika.utils.exceptions import ServiceException
from library.constants import (
    NOT_RAN,
    RESULT_FOUND,
    RESULT_FOUND_UPDATED,
    TASK_COMPLETED_STATUS,
)
from library.models import (
    LibraryEntry,
    LibraryEntrySuggestionsAlert,
    LibraryTask,
    Question,
    Questionnaire,
)
from library.services.question import QuestionService, get_default_question
from library.tests.factory import (
    EXISTING_QUESTION_ANSWER_TEXT,
    IMPORTED_QUESTION_ANSWER_TEXT,
    create_question,
    create_suggestion_alert,
    create_suggestion_questions,
)
from library.utils import get_question_by_id
from organization.models import Organization
from user.models import User
from user.tests import create_user


@contextmanager
def does_not_raise():
    yield


@pytest.fixture()
def default_question(graphql_organization: Organization) -> Question:
    return create_question(graphql_organization)


@pytest.fixture()
def suggestion_questions(
    graphql_organization: Organization,
) -> Tuple[Question, Question]:
    return create_suggestion_questions(graphql_organization)


@pytest.fixture()
def non_default_question(
    graphql_organization: Organization, default_question: Question
) -> Question:
    non_default = create_question(graphql_organization, default=False)
    default_question.equivalent_questions.add(non_default)
    return non_default


@pytest.fixture()
def fuzzy_matches(
    graphql_organization: Organization,
) -> List[Question]:
    fuzzy_match_1 = create_question(graphql_organization, question_text='FM1')
    fuzzy_match_2 = create_question(graphql_organization, question_text='FM2')
    fuzzy_match_3 = create_question(graphql_organization, question_text='FM3')
    return Question.objects.annotate(
        similarity=Case(
            When(text='FM1', then=Value(1)),
            default=(Value(random.uniform(0.2, 0.9))),
            output_field=FloatField(),
        )
    ).filter(id__in=[fuzzy_match_1.id, fuzzy_match_2.id, fuzzy_match_3.id])


@pytest.fixture()
def fuzzy_match_equivalent_question(
    graphql_organization: Organization,
) -> List[Question]:
    default_question = create_question(graphql_organization)
    fuzzy_match_1 = create_question(
        graphql_organization, question_text='FM1', default=False
    )
    default_question.equivalent_questions.add(fuzzy_match_1)
    return Question.objects.annotate(
        similarity=Case(
            When(text='FM1', then=Value(1)),
            default=(Value(random.uniform(0.2, 0.9))),
            output_field=FloatField(),
        )
    ).filter(id=fuzzy_match_1.id)


@pytest.fixture()
def user(graphql_organization: Organization) -> User:
    return create_user(graphql_organization, [], 'user+python+test@heylaika.com')


@pytest.fixture()
def default_library_task(user: User) -> LibraryTask:
    library_task = LibraryTask.objects.create(created_by=user)
    return library_task


@pytest.mark.functional()
def test_get_non_default_question(
    graphql_client, graphql_organization: Organization, non_default_question: Question
):
    question = get_question_by_id(
        organization_id=graphql_organization.id, question_id=non_default_question.id
    )

    assert question.id == non_default_question.id


@pytest.mark.functional()
def test_prevent_access_question_from_another_organization(
    graphql_client, different_organization: Organization, non_default_question: Question
):
    with pytest.raises(Question.DoesNotExist):
        get_question_by_id(
            organization_id=different_organization.id,
            question_id=non_default_question.id,
        )


@pytest.mark.functional()
def test_get_default_question(
    graphql_client, graphql_organization: Organization, default_question: Question
):
    question = get_default_question(
        organization_id=graphql_organization.id, question=default_question
    )

    assert question.id == default_question.id
    assert question.default is True


@pytest.mark.functional()
def test_prevent_access_default_question_from_another_organization(
    graphql_client,
    graphql_organization: Organization,
    different_organization: Organization,
    non_default_question: Question,
):
    non_default_question.default_question.equivalent_questions.remove(
        non_default_question
    )
    question_from_other_organization = create_question(
        different_organization, default=True
    )
    question_from_other_organization.equivalent_questions.add(non_default_question)
    with pytest.raises(Question.DoesNotExist):
        get_default_question(
            organization_id=graphql_organization.id, question=non_default_question
        )


@pytest.mark.functional()
def test_get_default_question_from_non_default_question(
    graphql_client,
    graphql_organization: Organization,
    default_question: Question,
    non_default_question: Question,
):
    default_question.equivalent_questions.add(non_default_question)
    question = get_default_question(
        organization_id=graphql_organization.id, question=non_default_question
    )

    assert question.id == default_question.id


@pytest.mark.parametrize(
    'status,expectation',
    [
        ('completed', does_not_raise()),
        ('in_progress', does_not_raise()),
        ('invalid', pytest.raises(ServiceException)),
    ],
)
def test_validate_question_status(status, expectation):
    with expectation:
        QuestionService.validate_question_status(status=status)


@pytest.mark.parametrize('old_completed,new_completed', [(False, True), (True, False)])
@pytest.mark.functional()
def test_update_question_complete(
    old_completed: bool, new_completed: bool, default_question: Question
):
    default_question.completed = old_completed
    default_question.save()

    updated_question = QuestionService.update_question_completion(
        question=default_question, new_complete_status=new_completed
    )

    assert updated_question.completed == new_completed


@pytest.mark.functional()
def test_get_questions(graphql_client, graphql_organization: Organization):
    for i in range(0, 2):
        create_question(graphql_organization, default=True)
    questions = QuestionService.get_questions(
        organization=graphql_organization, filter_params={'default': True}
    )

    assert len(questions) == 2


@pytest.mark.functional()
def test_get_questions_extra_params(graphql_client, graphql_organization: Organization):
    q1 = create_question(graphql_organization, default=True)
    q1.deleted_at = datetime.now(timezone.utc)
    q1.save()
    q2 = create_question(graphql_organization, default=True)
    questions = QuestionService.get_questions(
        organization=graphql_organization,
        filter_params={'default': True, 'deleted_at__isnull': True},
    )

    assert len(questions) == 1
    assert q2.id == questions[0].id


# skip by ts_rank not implemented in sqlite3 pytest
@pytest.mark.skip()
@pytest.mark.functional()
def test_search_questions(graphql_client, graphql_organization: Organization):
    create_question(graphql_organization, default=True, answer_text='Question 1')
    create_question(graphql_organization, default=True, answer_text='Question 2')
    q3 = create_question(
        graphql_organization,
        default=True,
        answer_text='Hey how are you? do you want chips?',
    )
    questions = QuestionService.search_questions(
        organization=graphql_organization,
        search_criteria='Hey',
        questions=QuestionService.get_questions(organization=graphql_organization),
        order_by=[],
    )

    assert len(questions) == 1
    assert q3.id == questions[0].id


@pytest.mark.functional()
def test_update_question_short_answer_fetched(
    graphql_organization: Organization, default_question: Question
):
    default_question.library_entry.short_answer_text = 'Short Answer Example'
    default_question.completed = True
    default_question.fetch_status = RESULT_FOUND
    default_question.save()
    updated_question = QuestionService.update_question_answer(
        organization_id=graphql_organization.id,
        question_id=default_question.id,
        answer_type='shortAnswer',
        answer_text='New Short Answer Example',
        user=create_user(graphql_organization, [], 'user+python+test@heylaika.com'),
    )
    assert not updated_question.completed
    assert updated_question.fetch_status == RESULT_FOUND
    assert (
        updated_question.library_entry.short_answer_text == 'New Short Answer Example'
    )
    assert default_question.library_entry.answer_text == 'Answer Example'


@pytest.mark.functional()
def test_update_question_short_answer_not_fetched(
    graphql_organization: Organization, default_question: Question
):
    default_question.library_entry.short_answer_text = 'Short Answer Example'
    default_question.completed = True
    default_question.fetch_status = NOT_RAN
    default_question.save()
    updated_question = QuestionService.update_question_answer(
        organization_id=graphql_organization.id,
        question_id=default_question.id,
        answer_type='shortAnswer',
        answer_text='New Short Answer Example',
        user=create_user(graphql_organization, [], 'user+python+test@heylaika.com'),
    )
    assert not updated_question.completed
    assert updated_question.fetch_status == NOT_RAN
    assert (
        updated_question.library_entry.short_answer_text == 'New Short Answer Example'
    )
    assert default_question.library_entry.answer_text == 'Answer Example'


@pytest.mark.functional()
def test_update_question_answer(
    graphql_organization: Organization, default_question: Question
):
    default_question.library_entry.short_answer_text = 'Short Answer Example'
    default_question.completed = True
    default_question.fetch_status = RESULT_FOUND
    default_question.save()
    updated_question = QuestionService.update_question_answer(
        organization_id=graphql_organization.id,
        question_id=default_question.id,
        answer_type='answer',
        answer_text='New Answer Example',
        user=create_user(graphql_organization, [], 'user+python+test@heylaika.com'),
    )
    assert not updated_question.completed
    assert updated_question.fetch_status == RESULT_FOUND_UPDATED
    assert updated_question.library_entry.answer_text == 'New Answer Example'
    assert default_question.library_entry.short_answer_text == 'Short Answer Example'


@pytest.mark.functional()
def test_update_question_answer_and_is_default_question(
    graphql_organization: Organization,
    default_question: Question,
    non_default_question: Question,
):
    default_question.library_entry.answer_text = 'Answer Example'
    default_question.library_entry.short_answer_text = 'Short Answer Example'
    default_question.save()
    non_default_question_2 = create_question(graphql_organization, default=False)
    default_question.equivalent_questions.add(
        *[non_default_question, non_default_question_2]
    )
    updated_question = QuestionService.update_question_answer(
        organization_id=graphql_organization.id,
        question_id=default_question.id,
        answer_type='answer',
        answer_text='New Answer Example',
        user=create_user(graphql_organization, [], 'user+python+test@heylaika.com'),
    )

    new_default_question_1 = Question.objects.get(id=non_default_question.id)
    new_default_question_2 = Question.objects.get(id=non_default_question_2.id)

    assert updated_question.equivalent_questions.count() == 0
    assert updated_question.default is True
    assert new_default_question_1.default is False
    assert new_default_question_2.default is True
    assert (
        new_default_question_2.equivalent_questions.filter(
            id__in=[new_default_question_1.id]
        ).count()
        == 1
    )


@pytest.mark.functional()
def test_update_question_short_answer_and_is_default_question(
    graphql_organization: Organization,
    default_question: Question,
    non_default_question: Question,
):
    default_question.library_entry.answer_text = 'Answer Example'
    default_question.library_entry.short_answer_text = 'Short Answer Example'
    default_question.save()
    non_default_question_2 = create_question(graphql_organization, default=False)
    default_question.equivalent_questions.add(
        *[non_default_question, non_default_question_2]
    )
    updated_question = QuestionService.update_question_answer(
        organization_id=graphql_organization.id,
        question_id=default_question.id,
        answer_type='shortAnswer',
        answer_text='New Short Answer Example',
        user=create_user(graphql_organization, [], 'user+python+test@heylaika.com'),
    )

    assert updated_question.equivalent_questions.count() == 2
    assert non_default_question.equivalent_questions.count() == 0
    assert non_default_question_2.equivalent_questions.count() == 0


@pytest.mark.functional()
def test_update_question_answer_and_is_non_default_question(
    graphql_organization: Organization,
    default_question: Question,
    non_default_question: Question,
):
    default_question.library_entry.answer_text = 'Answer Example'
    default_question.library_entry.short_answer_text = 'Short Answer Example'
    default_question.save()
    non_default_question_2 = create_question(graphql_organization, default=False)
    default_question.equivalent_questions.add(
        *[non_default_question, non_default_question_2]
    )
    updated_question = QuestionService.update_question_answer(
        organization_id=graphql_organization.id,
        question_id=non_default_question.id,
        answer_type='answer',
        answer_text='New Answer Example',
        user=create_user(graphql_organization, [], 'user+python+test@heylaika.com'),
    )

    default_question_updated = Question.objects.get(id=default_question.id)

    assert (
        default_question_updated.equivalent_questions.filter(
            id__in=[updated_question.id]
        ).count()
        == 0
    )
    assert default_question_updated.equivalent_questions.count() == 1
    assert updated_question.default is True


@pytest.mark.functional()
def test_update_question_short_answer_and_is_non_default_question(
    graphql_organization: Organization,
    default_question: Question,
    non_default_question: Question,
):
    default_question.library_entry.answer_text = 'Answer Example'
    default_question.library_entry.short_answer_text = 'Short Answer Example'
    default_question.save()
    non_default_question_2 = create_question(graphql_organization, default=False)
    default_question.equivalent_questions.add(
        *[non_default_question, non_default_question_2]
    )
    updated_question = QuestionService.update_question_answer(
        organization_id=graphql_organization.id,
        question_id=non_default_question.id,
        answer_type='shortAnswer',
        answer_text='New Short Answer Example',
        user=create_user(graphql_organization, [], 'user+python+test@heylaika.com'),
    )

    default_question_not_updated = Question.objects.get(id=default_question.id)

    assert (
        default_question_not_updated.equivalent_questions.filter(
            id__in=[updated_question.id]
        ).count()
        == 1
    )
    assert default_question_not_updated.equivalent_questions.count() == 2
    assert updated_question.default is False


@pytest.mark.functional()
def test_use_answer_should_add_equivalent_question(
    graphql_organization: Organization,
    default_question: Question,
    non_default_question: Question,
):
    default_question.library_entry.answer_text = 'Answer text'
    default_question.library_entry.short_answer_text = 'Short Answer text'
    default_question.library_entry.save()

    QuestionService.use_answer(
        organization_id=graphql_organization.id,
        question_id=default_question.id,
        equivalent_id=non_default_question.id,
    )

    assert non_default_question.equivalent_questions.count() == 0
    assert default_question.equivalent_questions.count() == 1


@pytest.mark.functional()
def test_use_answer_for_non_data_validated_fields(
    graphql_organization: Organization,
    default_question: Question,
    non_default_question: Question,
):
    default_question.library_entry.answer_text = 'Animal'
    default_question.library_entry.short_answer_text = 'Dog'
    default_question.library_entry.save()

    _, equivalent_question = QuestionService.use_answer(
        organization_id=graphql_organization.id,
        question_id=default_question.id,
        equivalent_id=non_default_question.id,
    )

    assert equivalent_question.library_entry.answer_text == 'Animal'
    assert equivalent_question.library_entry.short_answer_text == 'Dog'


@pytest.mark.functional()
def test_use_answer_for_matching_validated_fields(
    graphql_organization: Organization,
    default_question: Question,
    non_default_question: Question,
):
    default_question.library_entry.answer_text = 'Yes'
    default_question.library_entry.short_answer_text = 'No'
    default_question.library_entry.save()
    non_default_question.library_entry.metadata = {
        'answer': {'options': ['Yes', 'No']},
        'shortAnswer': {'options': ['Yes', 'No']},
    }
    non_default_question.library_entry.save()

    _, equivalent_question = QuestionService.use_answer(
        organization_id=graphql_organization.id,
        question_id=default_question.id,
        equivalent_id=non_default_question.id,
    )

    assert equivalent_question.library_entry.answer_text == 'Yes'
    assert equivalent_question.library_entry.short_answer_text == 'No'


@pytest.mark.functional()
def test_use_answer_from_equivalent_question(
    graphql_organization: Organization,
    default_question: Question,
    non_default_question: Question,
):
    non_default_question_2 = create_question(graphql_organization, default=False)
    non_default_question_2.library_entry.answer_text = 'Yes'
    non_default_question_2.library_entry.short_answer_text = 'No'
    non_default_question_2.library_entry.save()
    non_default_question.metadata = {
        'answer': {'options': ['yes', 'no']},
        'shortAnswer': {'options': ['yes', 'no']},
    }
    non_default_question.save()
    default_question.equivalent_questions.add(non_default_question_2)

    _, equivalent_question = QuestionService.use_answer(
        organization_id=graphql_organization.id,
        question_id=default_question.id,
        equivalent_id=non_default_question.id,
    )

    assert equivalent_question.library_entry.answer_text == 'Yes'
    assert equivalent_question.library_entry.short_answer_text == 'No'


@pytest.mark.functional()
@pytest.mark.parametrize(
    'answer_options,short_options,expected_answer,expected_short_answer',
    [
        (['OK', 'No'], ['Yes', 'No'], '', 'No'),
        (['Yes', 'No'], ['Yes', 'Ok'], 'Yes', ''),
        (['OK', 'Maybe'], ['Ok', 'Maybe'], '', ''),
    ],
)
def test_use_answer_for_non_matching_validated_fields(
    graphql_organization: Organization,
    default_question: Question,
    non_default_question: Question,
    answer_options: List[str],
    short_options: List[str],
    expected_answer: str,
    expected_short_answer: str,
):
    default_question.library_entry.answer_text = 'Yes'
    default_question.library_entry.short_answer_text = 'No'
    default_question.library_entry.save()
    non_default_question.metadata = {
        'answer': {'options': answer_options},
        'shortAnswer': {'options': short_options},
    }
    non_default_question.save()

    _, equivalent_question = QuestionService.use_answer(
        organization_id=graphql_organization.id,
        question_id=default_question.id,
        equivalent_id=non_default_question.id,
    )

    assert equivalent_question.library_entry.answer_text == expected_answer
    assert equivalent_question.library_entry.short_answer_text == expected_short_answer
    assert default_question.equivalent_questions.count() == 1


@pytest.mark.functional()
def test_use_answer_for_already_equivalent_question(
    graphql_organization: Organization,
    default_question: Question,
    non_default_question: Question,
):
    non_default_question.default_question.equivalent_questions.remove(
        non_default_question
    )
    default_question_2 = create_question(graphql_organization)
    default_question_2.equivalent_questions.add(non_default_question)

    _, equivalent_question = QuestionService.use_answer(
        organization_id=graphql_organization.id,
        question_id=default_question.id,
        equivalent_id=non_default_question.id,
    )

    assert default_question_2.equivalent_questions.count() == 0
    assert default_question.equivalent_questions.count() == 1


@pytest.mark.functional()
def test_use_answer_should_reset_fetch_and_completed(
    graphql_organization: Organization,
    default_question: Question,
    non_default_question: Question,
):
    non_default_question.fetch_status = RESULT_FOUND
    non_default_question.completed = True
    non_default_question.save()
    default_question_2 = create_question(graphql_organization)
    QuestionService.use_answer(
        organization_id=graphql_organization.id,
        question_id=default_question_2.id,
        equivalent_id=non_default_question.id,
    )

    references_count = Question.objects.filter(
        equivalent_questions__in=[non_default_question], id=default_question_2.id
    ).count()
    updated_non_default = Question.objects.get(id=non_default_question.id)
    assert updated_non_default.fetch_status == RESULT_FOUND_UPDATED
    assert not updated_non_default.completed
    assert default_question_2.equivalent_questions.count() == 1
    assert default_question.equivalent_questions.count() == 0
    assert references_count == 1


@pytest.mark.functional()
def test_update_question_text(
    graphql_organization: Organization, default_question: Question
):
    new_question_text = 'New Question Example'
    QuestionService.update_question_text(
        organization=graphql_organization,
        question_id=default_question.id,
        question_text=new_question_text,
    )
    question = Question.objects.get(
        id=default_question.id, library_entry__organization__id=graphql_organization.id
    )
    assert question.text == new_question_text


@pytest.mark.functional()
def test_update_question_library_entry_answer(
    graphql_organization: Organization, default_question: Question, user: User
):
    new_answer_text = 'New Answer'
    short_answer = default_question.library_entry.short_answer_text
    QuestionService.update_library_question_answer(
        question_to_update=default_question,
        user=user,
        answer_text=new_answer_text,
        short_answer_text=short_answer,
    )
    question = Question.objects.get(
        id=default_question.id, library_entry__organization__id=graphql_organization.id
    )
    assert question.library_entry.answer_text == new_answer_text
    assert question.library_entry.updated_by == user
    assert question.library_entry.short_answer_text == short_answer


@pytest.mark.functional()
def test_update_question_library_entry_short_answer(
    graphql_organization: Organization, default_question: Question, user: User
):
    new_short_answer_text = 'New Answer'
    answer_text = default_question.library_entry.answer_text
    QuestionService.update_library_question_answer(
        question_to_update=default_question,
        user=user,
        answer_text=answer_text,
        short_answer_text=new_short_answer_text,
    )
    question = Question.objects.get(
        id=default_question.id, library_entry__organization__id=graphql_organization.id
    )
    assert question.library_entry.short_answer_text == new_short_answer_text
    assert question.library_entry.answer_text == answer_text
    assert question.library_entry.updated_by == user


@pytest.mark.functional()
def test_update_question_library_entry_both_answers(
    graphql_organization: Organization, default_question: Question, user: User
):
    new_short_answer_text = 'New Answer'
    new_answer_text = 'New answer text'
    QuestionService.update_library_question_answer(
        question_to_update=default_question,
        user=user,
        answer_text=new_answer_text,
        short_answer_text=new_short_answer_text,
    )
    question = Question.objects.get(
        id=default_question.id, library_entry__organization__id=graphql_organization.id
    )
    assert question.library_entry.short_answer_text == new_short_answer_text
    assert question.library_entry.answer_text == new_answer_text
    assert question.library_entry.updated_by == user


@pytest.mark.functional()
def test_update_question_equivalent_questions_answer_not_update_short_answer(
    graphql_organization: Organization,
    user: User,
    default_question: Question,
    non_default_question: Question,
):
    non_default_question.library_entry.short_answer_text = 'Something'
    non_default_question.library_entry.save()
    default_question.equivalent_questions.add(non_default_question)
    QuestionService.update_library_question_answer(
        user=user,
        question_to_update=default_question,
        answer_text='New answer',
        short_answer_text='new short answer',
    )
    question = Question.objects.get(
        id=non_default_question.id,
        library_entry__organization__id=graphql_organization.id,
    )
    assert question.library_entry.short_answer_text == 'Something'
    assert question.library_entry.answer_text == 'New answer'
    assert question.library_entry.updated_by == user


@pytest.mark.functional()
def test_delete_library_question_without_equivalent_questions(
    graphql_organization: Organization,
    default_question: Question,
):
    QuestionService.delete_question_from_library(
        organization_id=graphql_organization.id,
        question_id=default_question.id,
    )
    assert not Question.objects.filter(
        id=default_question.id, library_entry__organization__id=graphql_organization.id
    ).exists()
    assert not LibraryEntry.objects.filter(
        question__id=default_question.id, organization__id=graphql_organization.id
    )


@pytest.mark.functional()
def test_delete_library_question_with_equivalent_questions_in_progress(
    graphql_organization: Organization,
    default_question: Question,
    non_default_question: Question,
):
    in_progress_questionnaire = Questionnaire.objects.create(
        name='Incomplete', organization=graphql_organization, completed=False
    )
    in_progress_questionnaire.questions.add(non_default_question)
    QuestionService.delete_question_from_library(
        organization_id=graphql_organization.id,
        question_id=default_question.id,
    )
    assert not Question.objects.filter(
        id=default_question.id, library_entry__organization__id=graphql_organization.id
    ).exists()
    assert not LibraryEntry.objects.filter(
        question__id=default_question.id, organization__id=graphql_organization.id
    )
    assert Question.objects.filter(
        id=non_default_question.id,
        library_entry__organization__id=graphql_organization.id,
        default=True,
    ).exists()


@pytest.mark.functional()
def test_delete_library_question_equivalent_questions_completed_questionnaire(
    graphql_organization: Organization,
    default_question: Question,
    non_default_question: Question,
):
    completed_questionnaire = Questionnaire.objects.create(
        name='Complete', organization=graphql_organization, completed=True
    )
    completed_questionnaire.questions.add(non_default_question)
    QuestionService.delete_question_from_library(
        organization_id=graphql_organization.id,
        question_id=default_question.id,
    )
    assert not Question.objects.filter(
        id=default_question.id, library_entry__organization__id=graphql_organization.id
    ).exists()
    assert not LibraryEntry.objects.filter(
        question__id=default_question.id, organization__id=graphql_organization.id
    )
    assert not Question.objects.filter(
        id=non_default_question.id,
        library_entry__organization__id=graphql_organization.id,
    ).exists()
    assert not LibraryEntry.objects.filter(
        question__id=non_default_question.id, organization__id=graphql_organization.id
    )


@pytest.mark.functional()
def test_delete_library_question_equivalent_questions_not_in_questionnaire(
    graphql_organization: Organization,
    default_question: Question,
    non_default_question: Question,
):
    QuestionService.delete_question_from_library(
        organization_id=graphql_organization.id,
        question_id=default_question.id,
    )
    assert not Question.objects.filter(
        id=default_question.id, library_entry__organization__id=graphql_organization.id
    ).exists()
    assert not LibraryEntry.objects.filter(
        question__id=default_question.id, organization__id=graphql_organization.id
    )
    assert not Question.objects.filter(
        id=non_default_question.id,
        library_entry__organization__id=graphql_organization.id,
    ).exists()
    assert not LibraryEntry.objects.filter(
        question__id=non_default_question.id, organization__id=graphql_organization.id
    )


@pytest.mark.functional()
def test_bulk_import_should_not_add_existing_question_and_answer(
    graphql_organization: Organization, default_question: Question
):
    records = QuestionService.bulk_import(
        rows=[
            {
                'Category': '',
                'Question': default_question.text,
                'Answer': default_question.library_entry.answer_text,
                'Short Answer': 'short text',
            }
        ],
        organization_id=graphql_organization.id,
    )
    same_question_and_answer_count = Question.objects.filter(
        text=default_question.text,
        library_entry__answer_text=default_question.library_entry.answer_text,
    ).count()
    assert len(records) == 0
    assert same_question_and_answer_count == 1


@pytest.mark.functional()
def test_bulk_import_should_add_existing_question_and_answer(
    graphql_organization: Organization,
):
    records = QuestionService.bulk_import(
        rows=[
            {
                'Category': '',
                'Question': 'New Question',
                'Answer': 'Answer-Text',
                'Short Answer': 'short text',
            }
        ],
        organization_id=graphql_organization.id,
    )
    question_exists = Question.objects.filter(
        text='New Question', library_entry__answer_text='Answer-Text'
    ).exists()
    assert len(records) == 1
    assert question_exists is True
    assert records[0].text == 'New Question'
    assert records[0].library_entry.answer_text == 'Answer-Text'
    assert records[0].library_entry.short_answer_text == 'short text'


@pytest.mark.functional()
def test_bulk_import_should_accept_empty_short_answer(
    graphql_organization: Organization,
):
    records = QuestionService.bulk_import(
        rows=[
            {
                'Category': '',
                'Question': 'New Question',
                'Answer': 'Answer-Text',
                'Short Answer': None,
            }
        ],
        organization_id=graphql_organization.id,
    )
    question_exists = Question.objects.filter(
        text='New Question', library_entry__answer_text='Answer-Text'
    ).exists()
    assert len(records) == 1
    assert question_exists is True
    assert records[0].text == 'New Question'
    assert records[0].library_entry.answer_text == 'Answer-Text'
    assert records[0].library_entry.short_answer_text == ''


@pytest.mark.functional()
def test_create_equivalent_suggestions_question_match_default_with_alert(
    user: User,
    default_question: Question,
    fuzzy_matches: List[Question],
    default_library_task: LibraryTask,
):
    with patch(
        'library.fetch.FetchFuzzyStrategy.get_question_matches',
        return_value=fuzzy_matches,
    ):
        latest_id = Question.objects.latest('id').id
        QuestionService.create_suggestions_for_questions(
            latest_id, [default_question], user, default_library_task.id
        )
        question_with_suggestion = Question.objects.get(
            id=fuzzy_matches[0].id,
        )
        equivalent_suggestions = question_with_suggestion.equivalent_suggestions.all()
        library_entry_suggestions_alerts = LibraryEntrySuggestionsAlert.objects.filter(
            organization=user.organization
        )
        library_task = LibraryTask.objects.get(id=default_library_task.id)

        assert len(equivalent_suggestions) == 1
        assert equivalent_suggestions.first().id == default_question.id
        assert library_entry_suggestions_alerts.count() == 1
        assert library_entry_suggestions_alerts.first().quantity == 1
        assert library_task.status == TASK_COMPLETED_STATUS


@pytest.mark.functional()
def test_bulk_import_should_add_question_without_category(
    graphql_organization: Organization,
):
    records = QuestionService.bulk_import(
        rows=[
            {
                'Category': None,
                'Question': 'new question',
                'Answer': 'answer',
                'Short Answer': 'short text',
            }
        ],
        organization_id=graphql_organization.id,
    )
    questions_count = Question.objects.filter(
        text='new question', library_entry__answer_text='answer'
    ).count()
    assert len(records) == 1
    assert questions_count == 1


@pytest.mark.functional()
def test_create_equivalent_suggestions_question_no_match(
    user: Organization, default_question: Question, default_library_task: LibraryTask
):
    with patch(
        'library.fetch.FetchFuzzyStrategy.get_question_matches',
        return_value=Question.objects.filter(text='Not Exist'),
    ):
        latest_id = Question.objects.latest('id').id
        QuestionService.create_suggestions_for_questions(
            latest_id, [default_question], user, default_library_task.id
        )
        questions_with_suggested_question = Question.objects.filter(
            equivalent_suggestions__id=default_question.id
        )
        library_entry_suggestions_alerts = LibraryEntrySuggestionsAlert.objects.filter(
            organization=user.organization
        )
        library_task = LibraryTask.objects.get(id=default_library_task.id)

        assert len(questions_with_suggested_question) == 0
        assert library_entry_suggestions_alerts.count() == 0
        assert library_task.status == TASK_COMPLETED_STATUS


@pytest.mark.functional()
def test_create_equivalent_suggestions_question_match_not_default(
    user: User,
    graphql_organization: Organization,
    fuzzy_match_equivalent_question: List[Question],
    default_library_task: LibraryTask,
):
    imported_question = create_question(graphql_organization)
    with patch(
        'library.fetch.FetchFuzzyStrategy.get_question_matches',
        return_value=fuzzy_match_equivalent_question,
    ):
        latest_id = Question.objects.latest('id').id
        QuestionService.create_suggestions_for_questions(
            latest_id, [imported_question], user, default_library_task.id
        )
        question_matched = Question.objects.get(
            id=fuzzy_match_equivalent_question[0].id
        )
        question_with_suggestion = question_matched.default_question
        equivalent_suggestions = question_with_suggestion.equivalent_suggestions.all()
        library_entry_suggestions_alerts = LibraryEntrySuggestionsAlert.objects.filter(
            organization=user.organization
        )
        library_task = LibraryTask.objects.get(id=default_library_task.id)

        assert len(equivalent_suggestions) == 1
        assert equivalent_suggestions.first().id == imported_question.id
        assert library_entry_suggestions_alerts.count() == 1
        assert library_entry_suggestions_alerts.first().quantity == 1
        assert library_task.status == TASK_COMPLETED_STATUS


@pytest.mark.functional()
def test_get_questions_with_suggestions(
    graphql_organization: Organization, default_question: Question
):
    other_question = create_question(graphql_organization)
    default_question.equivalent_suggestions.add(other_question)
    suggestions, has_suggestions = QuestionService.get_questions_with_suggestions(
        organization=graphql_organization
    )

    assert has_suggestions is True
    assert suggestions.count() == 1

    question_with_suggestions = suggestions[0]
    equivalent_suggestions = suggestions[0].equivalent_suggestions.all()

    assert question_with_suggestions.id == default_question.id
    assert equivalent_suggestions.count() == 1
    assert equivalent_suggestions[0].id == other_question.id


@pytest.mark.functional()
def test_get_questions_without_suggestions(
    graphql_organization: Organization,
):
    suggestions, has_suggestions = QuestionService.get_questions_with_suggestions(
        organization=graphql_organization
    )

    assert has_suggestions is False
    assert len(suggestions) == 0


@pytest.mark.functional()
def test_resolve_equivalent_suggestion_older_question_chosen(
    graphql_organization: Organization,
    user: User,
    suggestion_questions: Tuple[Question, Question],
):
    question_1, question_2 = suggestion_questions
    equivalent_question_from_question_1 = question_1.equivalent_questions.first()
    equivalent_question_from_question_2 = question_2.equivalent_questions.first()
    equivalent_suggestion_from_question_1 = question_1.equivalent_suggestions.first()
    equivalent_suggestion_from_question_2 = question_2.equivalent_suggestions.first()

    QuestionService.resolve_equivalent_suggestion(
        existing_question_id=question_1.id,
        equivalent_suggestion_id=question_2.id,
        chosen_question_id=question_1.id,
        answer_text='',
        organization=graphql_organization,
        user=user,
    )

    question_1_updated = Question.objects.get(id=question_1.id)
    question_2_updated = Question.objects.get(id=question_2.id)

    question_1_equivalent_questions = question_1_updated.equivalent_questions
    question_1_equivalent_suggestions = question_1_updated.equivalent_suggestions
    question_2_equivalent_questions = question_2_updated.equivalent_questions
    question_2_equivalent_suggestions = question_2_updated.equivalent_suggestions

    assert question_1_updated.library_entry.answer_text == EXISTING_QUESTION_ANSWER_TEXT
    assert question_2_updated.library_entry.answer_text == EXISTING_QUESTION_ANSWER_TEXT
    for equivalent_question in question_1_equivalent_questions.all():
        assert (
            equivalent_question.library_entry.answer_text
            == EXISTING_QUESTION_ANSWER_TEXT
        )

    assert len(question_1_equivalent_questions.all()) == 3
    assert len(question_2_equivalent_questions.all()) == 0

    assert (
        len(
            question_1_equivalent_questions.filter(
                id__in=[
                    equivalent_question_from_question_1.id,
                    equivalent_question_from_question_2.id,
                    question_2_updated.id,
                ]
            )
        )
        == 3
    )
    assert len(question_1_equivalent_suggestions.all()) == 2
    assert len(question_2_equivalent_suggestions.all()) == 0
    assert (
        len(
            question_1_equivalent_suggestions.filter(
                id__in=[
                    equivalent_suggestion_from_question_1.id,
                    equivalent_suggestion_from_question_2.id,
                ]
            )
        )
        == 2
    )
    assert len(question_1_equivalent_suggestions.filter(id=question_2_updated.id)) == 0


@pytest.mark.functional()
def test_resolve_equivalent_suggestion_newest_question_chosen(
    graphql_organization: Organization,
    user: User,
    suggestion_questions: Tuple[Question, Question],
):
    question_1, question_2 = suggestion_questions
    equivalent_question_from_question_1 = question_1.equivalent_questions.first()
    equivalent_question_from_question_2 = question_2.equivalent_questions.first()
    equivalent_suggestion_from_question_1 = question_1.equivalent_suggestions.first()
    equivalent_suggestion_from_question_2 = question_2.equivalent_suggestions.first()

    QuestionService.resolve_equivalent_suggestion(
        existing_question_id=question_1.id,
        equivalent_suggestion_id=question_2.id,
        chosen_question_id=question_2.id,
        answer_text='',
        organization=graphql_organization,
        user=user,
    )

    question_1_updated = Question.objects.get(id=question_1.id)
    question_2_updated = Question.objects.get(id=question_2.id)

    question_1_equivalent_questions = question_1_updated.equivalent_questions
    question_1_equivalent_suggestions = question_1_updated.equivalent_suggestions
    question_2_equivalent_questions = question_2_updated.equivalent_questions
    question_2_equivalent_suggestions = question_2_updated.equivalent_suggestions

    assert question_1_updated.library_entry.answer_text == IMPORTED_QUESTION_ANSWER_TEXT
    assert question_2_updated.library_entry.answer_text == IMPORTED_QUESTION_ANSWER_TEXT
    for equivalent_question in question_1_equivalent_questions.all():
        assert (
            equivalent_question.library_entry.answer_text
            == IMPORTED_QUESTION_ANSWER_TEXT
        )

    assert len(question_1_equivalent_questions.all()) == 3
    assert len(question_2_equivalent_questions.all()) == 0

    assert (
        len(
            question_1_equivalent_questions.filter(
                id__in=[
                    equivalent_question_from_question_1.id,
                    equivalent_question_from_question_2.id,
                    question_2_updated.id,
                ]
            )
        )
        == 3
    )
    assert len(question_1_equivalent_suggestions.all()) == 2
    assert len(question_2_equivalent_suggestions.all()) == 0
    assert (
        len(
            question_1_equivalent_suggestions.filter(
                id__in=[
                    equivalent_suggestion_from_question_1.id,
                    equivalent_suggestion_from_question_2.id,
                ]
            )
        )
        == 2
    )
    assert len(question_1_equivalent_suggestions.filter(id=question_2_updated.id)) == 0


@pytest.mark.functional()
def test_resolve_equivalent_suggestion_new_answer_chosen(
    graphql_organization: Organization,
    user: User,
    suggestion_questions: Tuple[Question, Question],
):
    NEW_ANSWER_TEXT = 'This is a new answer text'
    question_1, question_2 = suggestion_questions
    equivalent_question_from_question_1 = question_1.equivalent_questions.first()
    equivalent_question_from_question_2 = question_2.equivalent_questions.first()
    equivalent_suggestion_from_question_1 = question_1.equivalent_suggestions.first()
    equivalent_suggestion_from_question_2 = question_2.equivalent_suggestions.first()

    QuestionService.resolve_equivalent_suggestion(
        existing_question_id=question_1.id,
        equivalent_suggestion_id=question_2.id,
        chosen_question_id=0,
        answer_text=NEW_ANSWER_TEXT,
        organization=graphql_organization,
        user=user,
    )

    question_1_updated = Question.objects.get(id=question_1.id)
    question_2_updated = Question.objects.get(id=question_2.id)

    question_1_equivalent_questions = question_1_updated.equivalent_questions
    question_1_equivalent_suggestions = question_1_updated.equivalent_suggestions
    question_2_equivalent_questions = question_2_updated.equivalent_questions
    question_2_equivalent_suggestions = question_2_updated.equivalent_suggestions

    assert question_1_updated.library_entry.answer_text == NEW_ANSWER_TEXT
    assert question_2_updated.library_entry.answer_text == NEW_ANSWER_TEXT
    for equivalent_question in question_1_equivalent_questions.all():
        assert equivalent_question.library_entry.answer_text == NEW_ANSWER_TEXT
    for equivalent_question in question_2_equivalent_questions.all():
        assert equivalent_question.library_entry.answer_text == NEW_ANSWER_TEXT

    assert len(question_1_equivalent_questions.all()) == 3
    assert len(question_2_equivalent_questions.all()) == 0

    assert (
        len(
            question_1_equivalent_questions.filter(
                id__in=[
                    equivalent_question_from_question_1.id,
                    equivalent_question_from_question_2.id,
                    question_2_updated.id,
                ]
            )
        )
        == 3
    )
    assert len(question_1_equivalent_suggestions.all()) == 2
    assert len(question_2_equivalent_suggestions.all()) == 0
    assert (
        len(
            question_1_equivalent_suggestions.filter(
                id__in=[
                    equivalent_suggestion_from_question_1.id,
                    equivalent_suggestion_from_question_2.id,
                ]
            )
        )
        == 2
    )
    assert len(question_1_equivalent_suggestions.filter(id=question_2_updated.id)) == 0


@pytest.mark.functional()
def test_resolve_equivalent_suggestion_keep_separate_entries(
    graphql_organization: Organization,
    user: User,
    suggestion_questions: Tuple[Question, Question],
):
    question_1, question_2 = suggestion_questions
    question_1_original_answer = question_1.library_entry.answer_text
    question_2_original_answer = question_2.library_entry.answer_text
    equivalent_question_from_question_1 = question_1.equivalent_questions.first()
    equivalent_question_from_question_2 = question_2.equivalent_questions.first()
    equivalent_suggestion_from_question_1 = question_1.equivalent_suggestions.first()
    equivalent_suggestion_from_question_2 = question_2.equivalent_suggestions.first()

    QuestionService.resolve_equivalent_suggestion(
        existing_question_id=question_1.id,
        equivalent_suggestion_id=question_2.id,
        chosen_question_id=0,
        answer_text='',
        organization=graphql_organization,
        user=user,
    )

    question_1_updated = Question.objects.get(id=question_1.id)
    question_2_updated = Question.objects.get(id=question_2.id)

    question_1_equivalent_questions = question_1_updated.equivalent_questions
    question_1_equivalent_suggestions = question_1_updated.equivalent_suggestions
    question_2_equivalent_questions = question_2_updated.equivalent_questions
    question_2_equivalent_suggestions = question_2_updated.equivalent_suggestions

    assert question_1_updated.library_entry.answer_text == question_1_original_answer
    assert question_2_updated.library_entry.answer_text == question_2_original_answer
    for equivalent_question in question_1_equivalent_questions.all():
        assert (
            equivalent_question.library_entry.answer_text == question_1_original_answer
        )
    for equivalent_question in question_2_equivalent_questions.all():
        assert (
            equivalent_question.library_entry.answer_text == question_2_original_answer
        )

    assert len(question_1_equivalent_questions.all()) == 1
    assert len(question_2_equivalent_questions.all()) == 1

    assert (
        question_1_equivalent_questions.first().id
        == equivalent_question_from_question_1.id
    )

    assert (
        question_2_equivalent_questions.first().id
        == equivalent_question_from_question_2.id
    )

    assert len(question_1_equivalent_suggestions.all()) == 1
    assert len(question_2_equivalent_suggestions.all()) == 1

    assert (
        question_1_equivalent_suggestions.first().id
        == equivalent_suggestion_from_question_1.id
    )

    assert (
        question_2_equivalent_suggestions.first().id
        == equivalent_suggestion_from_question_2.id
    )


@pytest.mark.functional()
def test_remove_suggestion_alert(
    user: User,
):
    suggestion_quantity = 1
    create_suggestion_alert(user, suggestion_quantity)
    QuestionService.remove_suggestions_alert(user.organization)
    alert = LibraryEntrySuggestionsAlert.objects.filter(organization=user.organization)
    assert alert.count() == 0

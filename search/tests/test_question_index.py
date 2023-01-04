from datetime import datetime, timedelta

import pytest

from library.models import Question
from search.indexing.question_index import question_search_index
from search.models import Index


@pytest.mark.functional
def test_question_search_mapper_fetch_draft(question):
    response = question_search_index.mapper(
        question, fetch_publish=True, published=False
    )

    assert response.id == f'question-{question.id}'
    assert response.fields.organization_id == str(
        question.library_entry.organization_id
    )
    assert response.fields.category == []
    assert response.fields.is_draft == 0


@pytest.mark.functional
def test_question_search_mapper_no_draft_fetch(question):
    response = question_search_index.mapper(
        question, fetch_publish=False, published=False
    )

    assert response.id == f'question-{question.id}'
    assert response.fields.organization_id == str(
        question.library_entry.organization_id
    )
    assert response.fields.category == []
    assert response.fields.is_draft == 1


@pytest.mark.functional
def test_get_new_index_records(question: Question, default_question: Question):
    results = question_search_index.get_new_index_records_queryset(
        [default_question.id]
    )

    assert results.count() == 1
    assert results[0].id == question.id


@pytest.mark.functional
def test_get_updated_index_records(question: Question, default_question: Question):
    last_day = datetime.today() - timedelta(days=1)
    last_week = datetime.now() - timedelta(days=7)
    Question.objects.filter(pk=question.pk).update(updated_at=last_week)
    results = question_search_index.get_updated_index_records(from_date=last_day)

    assert results.count() == 1
    assert results[0].id == default_question.id


@pytest.mark.functional
def test_get_deleted_index_records(default_question: Question):
    Index.objects.create(
        type=question_search_index.RESOURCE_TYPE, key='random-question-id'
    )
    Index.objects.create(
        type=question_search_index.RESOURCE_TYPE, key=str(default_question.id)
    )

    results = question_search_index.get_deleted_index_records(Index.objects.all())

    assert results.count() == 1
    assert results[0].key == 'random-question-id'

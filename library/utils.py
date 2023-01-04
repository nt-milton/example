import logging
from typing import List, Optional, Tuple

from django.contrib.postgres.search import SearchRank, SearchVector
from django.db.models import Q, TextField, Value
from django.db.models.functions import Replace, Trim

from laika.constants import CATEGORIES, WSEventTypes
from laika.utils.exceptions import ServiceException
from laika.utils.websocket import send_message
from library.constants import NO_RESULT, RESULT_FOUND, STATUS_COMPLETED
from library.filters import (
    filter_by_assignee,
    filter_by_fetch,
    filter_by_search,
    filter_by_status,
    get_assignee_filters,
    get_fetch_filters,
    get_status_filters,
)
from library.models import LibraryEntry, Question, Questionnaire
from organization.models import Organization
from search.indexing.question_index import question_search_index
from search.utils import PartialSearchQuery, search_query

logger = logging.getLogger('library')

# Used in seeder
LIBRARY_FIELDS = ['answer', 'category', 'question', 'short_answer']
LIBRARY_REQUIRED_FIELDS = ['answer', 'category', 'question']

ICON_NAME = 'class'
ICON_COLOR = 'brandViolet'
SHORT_ANSWER = 'Short Answer'


def get_question_by_id(*, organization_id: str, question_id: int):
    return Question.objects.get(
        id=question_id, library_entry__organization__id=organization_id
    )


def are_questions_valid(organization, default, aliases):
    aliases_in_default_exists = Question.objects.filter(
        text__in=aliases, default=True, library_entry__organization=organization
    ).exists()
    default_in_aliases_exists = Question.objects.filter(
        text=default, default=False, library_entry__organization=organization
    ).exists()

    return not (default_in_aliases_exists and aliases_in_default_exists)


def create_question(entry, question_text, default=False):
    return Question.objects.create(
        text=question_text, default=default, library_entry=entry
    )


def search_questions(organization, search_criteria, qs):
    vector = SearchVector('question__text', weight='A') + SearchVector(
        'answer_text', weight='B'
    )
    query = PartialSearchQuery(search_criteria)
    rank = SearchRank(vector, query)

    results = search_query(organization, LibraryEntry, qs, rank)

    ids = []
    unique_result = []
    # This is because the django search can return duplicated records,
    # but with a little change on the rank field amount.
    for r in results:
        if r.id not in ids:
            unique_result.append(r)
            ids.append(r.id)

    return unique_result


def is_category_valid(category):
    return any([name for name, y in CATEGORIES if category.strip() == name])


def update_questionnaire_status(questionnaires: List[Questionnaire], status: str):
    new_questionnaires = []
    for questionnaire in questionnaires:
        questionnaire.completed = status == STATUS_COMPLETED
        if questionnaire.completed:
            soft_deleted_questions = Question.all_objects.filter(
                deleted_at__isnull=False, questionnaires__id=questionnaire.id
            )
            for question in soft_deleted_questions:
                question.hard_delete()

        new_questionnaires.append(questionnaire)

    return new_questionnaires


def update_library_question_status(
    question_id: str, organization: Organization, status: str
):
    question_to_update = Question.objects.filter(
        library_entry__organization=organization, id=question_id
    )

    if not question_to_update:
        raise ServiceException('Question not found')

    new_status = status == STATUS_COMPLETED
    question_to_update.update(completed=new_status)


def get_organization_question_filters(
    questionnaire: Questionnaire, organization: Organization
):
    return [
        get_fetch_filters(),
        get_status_filters(),
        get_assignee_filters(questionnaire, organization),
    ]


def get_questionnaire_details_filters(selected_filters: dict):
    filters = Q()
    filters &= filter_by_fetch(selected_filters)
    filters &= filter_by_assignee(selected_filters)
    filters &= filter_by_status(selected_filters)
    filters &= filter_by_search(selected_filters)
    return filters


def get_questions_annotate_for_fetch():
    return Question.objects.annotate(
        question_without_line_breaks=Replace(
            Trim('text'),
            Value('\n', output_field=TextField()),
            Value('', output_field=TextField()),
        ),
        question_without_tabs=Replace(
            Trim('question_without_line_breaks'),
            Value('\t', output_field=TextField()),
            Value('', output_field=TextField()),
        ),
        question_without_carriage_return=Replace(
            Trim('question_without_tabs'),
            Value('\r', output_field=TextField()),
            Value('', output_field=TextField()),
        ),
        question_without_spaces=Replace(
            Trim('question_without_carriage_return'),
            Value(' ', output_field=TextField()),
            Value('', output_field=TextField()),
        ),
    )


def get_question_validated_options(*, question: Question, field: str, mapper=None):
    options = question.metadata.get(field, {}).get('options', [])
    return [mapper(option) for option in options] if mapper else options


def can_use_answer(
    *, from_question: Question, field: str, target_question: Question
) -> Tuple[bool, Optional[Question]]:
    options = get_question_validated_options(question=target_question, field=field)
    question_ids = [
        from_question.id,
        *from_question.equivalent_questions.values_list('id', flat=True),
    ]
    options_filter = Q()
    filters = Q(id__in=question_ids)
    for option in options:
        q = (
            Q(library_entry__answer_text__iexact=str(option))
            if field == 'answer'
            else Q(library_entry__short_answer_text__iexact=str(option))
        )
        options_filter |= q
    filters &= Q(options_filter)
    match = Question.objects.filter(filters).exclude(id=target_question.id).first()
    return (True, match) if match else (False, None)


def update_answer_based_on_match(*, from_question: Question, target_question: Question):
    can_use_long_answer, match = can_use_answer(
        target_question=target_question, field='answer', from_question=from_question
    )
    can_use_short_answer, match_short = can_use_answer(
        target_question=target_question,
        field='shortAnswer',
        from_question=from_question,
    )

    if can_use_long_answer and match:
        target_question.library_entry.answer_text = match.library_entry.answer_text

    if can_use_short_answer and match_short:
        target_question.library_entry.short_answer_text = (
            match_short.library_entry.short_answer_text
        )
    target_question.library_entry.save()


def validate_match_assign_answer_text(
    match: Optional[Question],
    question: Question,
    questions_fetched: List[Question],
    non_fetched_questions: List[Question],
):
    if match:
        question.default_question.equivalent_questions.remove(question)
        match.default_question.equivalent_questions.add(question)

        update_answer_based_on_match(target_question=question, from_question=match)

        question.fetch_status = RESULT_FOUND
        question.default = False
        questions_fetched.append(question)
    else:
        question.fetch_status = NO_RESULT
        non_fetched_questions.append(question)
    question.save()


def notify_library_entry_answer_modification(
    info, entry: LibraryEntry, questions: List[Question]
):
    library_entry = {
        'id': entry.id,
        'answer': entry.answer_text,
        'shortAnswer': entry.short_answer_text,
    }
    send_message(
        info,
        WSEventTypes.LIBRARY_QUESTION_ANSWERED.value,
        logger=logger,
        payload={
            'questions': [
                {
                    'id': question.id,
                    'text': question.text,
                    'libraryEntry': library_entry,
                    'metadata': question.metadata,
                }
                for question in questions
            ]
        },
    )


def update_questions_index_by_questionnaire(questionnaire_id: str, published: bool):
    questions_to_update_index = Question.objects.filter(
        questionnaires__id=questionnaire_id
    ).select_related('library_entry')

    question_search_index.add_to_index(questions_to_update_index, False, published)


def is_question_in_equivalent_suggestions(
    question: Question, equivalent_suggestion: Question
) -> bool:
    return question.equivalent_suggestions.filter(id=equivalent_suggestion.id).exists()


def get_suggestion_questions(
    existing_question_id: int,
    equivalent_suggestion_id: int,
    chosen_question_id: int,
    organization: Organization,
):
    try:
        existing_question = get_question_by_id(
            organization_id=organization.id, question_id=existing_question_id
        )
        equivalent_suggestion = get_question_by_id(
            organization_id=organization.id, question_id=equivalent_suggestion_id
        )

        if not is_question_in_equivalent_suggestions(
            question=existing_question, equivalent_suggestion=equivalent_suggestion
        ):
            raise ServiceException(
                '''
                    Existing library question does not have equivalent
                    library question as suggestion
                '''
            )

        if chosen_question_id and (
            existing_question_id != chosen_question_id
            and equivalent_suggestion_id != chosen_question_id
        ):
            raise ServiceException(
                '''
                    Chosen question id does not match any question
                    in the suggestion
                '''
            )

        return existing_question, equivalent_suggestion

    except Question.DoesNotExist:
        raise ServiceException(
            '''
                Either the existing library question or equivalent
                library question does not exist
            '''
        )

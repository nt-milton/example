import logging
from datetime import datetime
from multiprocessing.pool import ThreadPool
from typing import List, Tuple

from django.contrib.postgres.search import SearchRank, SearchVector
from django.db.models import Q

from alert.constants import ALERT_TYPES
from alert.models import Alert
from laika.utils.exceptions import ServiceException
from laika.utils.order_by import get_order_queries
from library.constants import (
    LIBRARY_ANSWER_TYPE,
    LIBRARY_SHORT_ANSWER_TYPE,
    RESULT_FOUND,
    RESULT_FOUND_UPDATED,
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    TASK_COMPLETED_STATUS,
    TASK_ERROR_STATUS,
    TASK_IN_PROGRESS_STATUS,
    FetchType,
)
from library.fetch import Fetch
from library.models import (
    LibraryEntry,
    LibraryEntrySuggestionsAlert,
    LibraryTask,
    Question,
)
from library.utils import (
    get_question_by_id,
    get_question_validated_options,
    get_suggestion_questions,
    update_answer_based_on_match,
)
from organization.models import Organization
from search.utils import PartialSearchQuery, search_query
from user.models import User

pool = ThreadPool()
logger = logging.getLogger(__name__)

LIBRARY_ANSWER_TYPE_FIELDS = ['answer', 'shortAnswer']


def get_default_question(*, organization_id: str, question: Question):
    return (
        question
        if question.default
        else Question.objects.get(
            default=True,
            equivalent_questions__id=question.id,
            library_entry__organization__id=organization_id,
        )
    )


def get_default_question_by_id(*, organization_id: str, question_id: int):
    return Question.objects.get(
        id=question_id, library_entry__organization__id=organization_id, default=True
    )


def remove_equivalent_question(*, question: Question, equivalent_question: Question):
    equivalent_question.default = True
    equivalent_question.save()
    question.equivalent_questions.remove(equivalent_question)


def add_equivalent_question(
    *, default_question: Question, equivalent_question: Question
):
    equivalent_question.default = False
    equivalent_question.save()

    default_question.equivalent_questions.add(equivalent_question)


def get_equivalent_questions_for_in_progress_questionnaire(*, question: Question):
    return question.equivalent_questions.filter(
        questionnaires__completed=False, deleted_at__isnull=True
    )


def get_equivalent_questions_for_completed_questionnaire(*, question: Question):
    return question.equivalent_questions.filter(
        Q(Q(questionnaires__isnull=True) | Q(questionnaires__completed=True)),
        deleted_at__isnull=True,
    )


class QuestionService:
    @staticmethod
    def validate_question_status(*, status: str):
        if status not in [STATUS_COMPLETED, STATUS_IN_PROGRESS]:
            raise ServiceException('Invalid new status for question')

    @staticmethod
    def update_question_completion(
        *, question: Question, new_complete_status: bool
    ) -> Question:
        question.completed = new_complete_status
        question.save()
        return question

    @staticmethod
    def add_equivalent_question(
        *, organization_id: str, question_id: int, equivalent_question_id: int
    ):
        question = get_default_question_by_id(
            organization_id=organization_id, question_id=question_id
        )
        equivalent_question = get_question_by_id(
            organization_id=organization_id, question_id=equivalent_question_id
        )
        add_equivalent_question(
            default_question=question, equivalent_question=equivalent_question
        )

    @staticmethod
    def remove_equivalent_question(
        *, organization_id: str, question_id: int, equivalent_question_id: int
    ):
        question = get_default_question_by_id(
            organization_id=organization_id, question_id=question_id
        )
        equivalent_question = get_question_by_id(
            organization_id=organization_id, question_id=equivalent_question_id
        )
        remove_equivalent_question(
            question=question, equivalent_question=equivalent_question
        )

    @staticmethod
    def assign_user_to_question(
        *, organization_id: str, question_id: int, user_assigned: User
    ) -> Question:
        question = get_question_by_id(
            organization_id=organization_id, question_id=question_id
        )
        question.user_assigned = user_assigned
        question.save()
        return question

    @staticmethod
    def get_questions(
        *, organization: Organization, filter_params: dict = {}
    ) -> Question:
        questions = Question.objects.filter(
            library_entry__organization=organization, **filter_params
        )
        return questions

    @staticmethod
    def search_questions(
        *,
        organization: Organization,
        search_criteria: str,
        questions: List[Question],
        order_by: List[dict],
    ):
        vector = SearchVector('text', weight='A') + SearchVector(
            'library_entry__answer_text', weight='B'
        )
        query = PartialSearchQuery(search_criteria)
        rank = SearchRank(vector, query)

        results = search_query(organization, Question, questions, rank).order_by(
            *get_order_queries(order_by)
        )

        ids = []
        unique_result = []
        # This is because the django search can return duplicated records,
        # but with a little change on the rank field amount.
        for r in results:
            if r.id not in ids:
                unique_result.append(r)
                ids.append(r.id)

        return unique_result

    @staticmethod
    def get_library_questions(
        *, organization: Organization, order_by: List[dict], filter_data: str = ''
    ) -> Tuple[List[Question], bool]:
        library_questions = (
            QuestionService.get_questions(
                organization=organization,
                filter_params={'default': True, 'deleted_at__isnull': True},
            )
            .select_related('library_entry')
            .filter(Q(questionnaires__completed=True) | Q(questionnaires__isnull=True))
            .order_by(*get_order_queries(order_by))
        )

        has_library_questions = library_questions.count() > 0

        if filter_data:
            library_questions = QuestionService.search_questions(
                organization=organization,
                search_criteria=filter_data,
                questions=library_questions,
                order_by=order_by,
            )
        return library_questions, has_library_questions

    @staticmethod
    def update_question_answer(
        *,
        organization_id: str,
        question_id: int,
        answer_type: str,
        answer_text: str,
        user: User,
    ) -> Question:
        if answer_type not in LIBRARY_ANSWER_TYPE_FIELDS:
            raise ServiceException('Invalid answer type for updating question')

        question = get_question_by_id(
            organization_id=organization_id, question_id=question_id
        )
        if (
            question.library_entry.answer_text != answer_text
            and answer_type == LIBRARY_ANSWER_TYPE
        ):
            question.reconcile_equivalent_questions()
        if answer_type == LIBRARY_SHORT_ANSWER_TYPE:
            question.library_entry.short_answer_text = answer_text
        elif answer_type == LIBRARY_ANSWER_TYPE:
            question.library_entry.answer_text = answer_text
            if question.fetch_status == RESULT_FOUND:
                question.fetch_status = RESULT_FOUND_UPDATED
        question.library_entry.updated_at = datetime.now()
        question.library_entry.updated_by = user
        question.completed = False
        question.library_entry.save()
        question.save()
        return question

    @staticmethod
    def use_answer(*, organization_id: str, question_id: int, equivalent_id: int):
        question = get_question_by_id(
            organization_id=organization_id, question_id=question_id
        )
        equivalent_question = get_question_by_id(
            organization_id=organization_id, question_id=equivalent_id
        )
        remove_equivalent_question(
            question=equivalent_question.default_question,
            equivalent_question=equivalent_question,
        )
        equivalent_question.library_entry.answer_text = ''
        equivalent_question.library_entry.short_answer_text = ''

        update_answer_based_on_match(
            target_question=equivalent_question, from_question=question
        )

        add_equivalent_question(
            default_question=question, equivalent_question=equivalent_question
        )
        if equivalent_question.fetch_status == RESULT_FOUND:
            equivalent_question.fetch_status = RESULT_FOUND_UPDATED
        equivalent_question.completed = False
        equivalent_question.save()
        return question, equivalent_question

    @staticmethod
    def reconcile_answer_when_creating_question(question: Question):
        answer_text = question.library_entry.answer_text.lower()
        short_text = question.library_entry.short_answer_text.lower()

        def lower_case_mapper(option):
            return option.lower()

        answer_options = get_question_validated_options(
            question=question, field='answer', mapper=lower_case_mapper
        )
        short_options = get_question_validated_options(
            question=question, field='shortAnswer', mapper=lower_case_mapper
        )

        if answer_options and answer_text not in answer_options:
            question.library_entry.answer_text = ''
            question.reconcile_equivalent_questions()

        if short_options and short_text not in short_options:
            question.library_entry.short_answer_text = ''

        question.library_entry.save()

    @staticmethod
    def update_question_text(
        *, organization: Organization, question_id: int, question_text: str
    ):
        question = get_default_question_by_id(
            organization_id=organization.id, question_id=question_id
        )
        if not question:
            return
        question.text = question_text
        question.updated_at = datetime.now()
        question.save()

    @staticmethod
    def __update_question_from_library(
        *,
        question: Question,
        user: User,
        answer_text: str,
        short_answer_text: str,
        can_update_short_answer: bool = True,
    ):
        """
        Updating a question from library should let you update any field,
        and it's going to keep the equivalent questions.
        """
        question.library_entry.answer_text = answer_text
        if can_update_short_answer:
            question.library_entry.short_answer_text = short_answer_text

        question.library_entry.updated_at = datetime.now()
        question.library_entry.updated_by = user
        question.library_entry.save()

    @staticmethod
    def update_library_question_answer(
        question_to_update: Question,
        user: User,
        answer_text: str = '',
        short_answer_text: str = '',
    ):
        QuestionService.__update_question_from_library(
            question=question_to_update,
            user=user,
            answer_text=answer_text,
            short_answer_text=short_answer_text,
        )
        equivalent_questions = question_to_update.equivalent_questions.all()
        for question in equivalent_questions:
            QuestionService.__update_question_from_library(
                question=question,
                user=user,
                answer_text=answer_text,
                short_answer_text=short_answer_text,
                can_update_short_answer=False,
            )

    @staticmethod
    def delete_question_from_library(organization_id: str, question_id: int):
        question_to_delete = get_question_by_id(
            organization_id=organization_id, question_id=question_id
        )
        equivalent_questions_in_progress = (
            get_equivalent_questions_for_in_progress_questionnaire(
                question=question_to_delete
            )
        )
        for equivalent_question in equivalent_questions_in_progress:
            remove_equivalent_question(
                question=question_to_delete, equivalent_question=equivalent_question
            )
        equivalent_questions_completed = (
            get_equivalent_questions_for_completed_questionnaire(
                question=question_to_delete
            )
        )
        for equivalent_question in equivalent_questions_completed:
            equivalent_question.delete()
            equivalent_question.library_entry.delete()
        question_to_delete.delete()
        question_to_delete.library_entry.delete()

    @staticmethod
    def bulk_import(rows, organization_id: str):
        records = []
        for row in rows:
            filter_existing_question = Q(
                text=row['Question'],
                library_entry__answer_text=row['Answer'],
                library_entry__organization_id=organization_id,
            ) & (Q(questionnaires__completed=True) | Q(questionnaires__isnull=True))
            if Question.objects.filter(filter_existing_question).exists():
                continue
            new_entry = LibraryEntry.objects.create(
                organization_id=organization_id,
                answer_text=row['Answer'],
                short_answer_text=(row['Short Answer'] if row['Short Answer'] else ''),
                category=row['Category'] or '',
            )
            new_question = Question.objects.create(
                text=row['Question'], default=True, library_entry=new_entry
            )
            records.append(new_question)
        return records

    @staticmethod
    def __get_suggestion_matches(
        latest_id: int, questions: List[Question], organization: Organization
    ):
        fetch_fuzzy_strategy = Fetch(FetchType.FUZZY.value).strategy
        processed_ids = []
        matches = []
        for question in questions:
            fuzzy_matches = (
                fetch_fuzzy_strategy.get_question_matches(
                    question,
                    organization,
                    0.2,
                )
                .exclude(
                    id__in=[question.id for question in questions],
                )
                .exclude(
                    id__gt=latest_id,
                )
            )

            if len(fuzzy_matches) == 0:
                processed_ids.append(question.id)
            else:
                for fuzzy_match in fuzzy_matches:
                    matches.append((fuzzy_match, question))
        matches.sort(key=lambda tup: tup[0].similarity, reverse=True)
        return matches, processed_ids

    @staticmethod
    def create_suggestions_for_questions(
        latest_id: int, questions: List[Question], user: User, library_task_id: int
    ):
        library_task = LibraryTask.objects.get(id=library_task_id)
        library_task.status = TASK_IN_PROGRESS_STATUS
        library_task.updated_at = datetime.now()
        library_task.save()
        matches, processed_ids = QuestionService.__get_suggestion_matches(
            latest_id, questions, user.organization
        )
        suggestions_to_create = {}

        for fuzzy_match_tuple in matches:
            existing_question, imported_question = fuzzy_match_tuple
            if len(processed_ids) == len(questions):
                break
            if (
                existing_question.id in suggestions_to_create
                or imported_question.id in processed_ids
            ):
                continue
            suggestions_to_create[existing_question.id] = fuzzy_match_tuple
            processed_ids.append(imported_question.id)

        if len(suggestions_to_create) > 0:
            QuestionService.add_suggestions_questions(
                user, suggestions_to_create, library_task
            )
        else:
            library_task.status = TASK_COMPLETED_STATUS
            library_task.updated_at = datetime.now()
            library_task.save()

    @staticmethod
    def add_suggestions_questions(
        user: User, suggestions: dict, library_task: LibraryTask
    ):
        try:
            for key in suggestions:
                suggestion = suggestions[key]
                question = suggestion[0]
                question.default_question.equivalent_suggestions.add(suggestion[1])
            QuestionService.create_suggestions_alerts(user, len(suggestions))
            library_task.status = TASK_COMPLETED_STATUS
        except Exception as error:
            logger.exception(f'Error when creating suggestions. Error {error}')
            library_task.status = TASK_ERROR_STATUS
        finally:
            library_task.updated_at = datetime.now()
            library_task.save()

    @staticmethod
    def create_suggestions_alerts(user: User, quantity: int):
        LibraryEntrySuggestionsAlert.objects.custom_create(
            quantity=quantity,
            organization=user.organization,
            sender=user,
            receiver=user,
            alert_type=ALERT_TYPES['LIBRARY_ENTRY_SUGGESTIONS'],
        )

    @staticmethod
    def get_questions_with_suggestions(*, organization: Organization):
        suggestions = Question.objects.filter(
            library_entry__organization=organization,
            equivalent_suggestions__isnull=False,
        ).distinct()

        has_suggestions = suggestions.count() > 0

        return suggestions, has_suggestions

    @staticmethod
    def __merge_suggestions(
        *,
        existing_question: Question,
        equivalent_suggestion: Question,
        chosen_question_id: int,
        answer_text: str,
        user: User,
    ):
        if not chosen_question_id:
            QuestionService.update_library_question_answer(
                question_to_update=existing_question,
                user=user,
                answer_text=answer_text,
                short_answer_text=existing_question.library_entry.short_answer_text,
            )
            QuestionService.update_library_question_answer(
                question_to_update=equivalent_suggestion,
                user=user,
                answer_text=answer_text,
                short_answer_text=equivalent_suggestion.library_entry.short_answer_text,
            )
            return

        question_to_use, question_to_update = (
            (existing_question, equivalent_suggestion)
            if existing_question.id == chosen_question_id
            else (equivalent_suggestion, existing_question)
        )
        update_answer_based_on_match(
            target_question=question_to_update, from_question=question_to_use
        )
        equivalent_questions = question_to_update.equivalent_questions.all()
        for equivalent_question in equivalent_questions:
            update_answer_based_on_match(
                target_question=equivalent_question, from_question=question_to_use
            )

    @staticmethod
    def resolve_equivalent_suggestion(
        existing_question_id: int,
        equivalent_suggestion_id: int,
        chosen_question_id: int,
        answer_text: str,
        organization: Organization,
        user: User,
    ):
        existing_question, equivalent_suggestion = get_suggestion_questions(
            existing_question_id,
            equivalent_suggestion_id,
            chosen_question_id,
            organization=organization,
        )

        should_merge_suggestions = bool(chosen_question_id or answer_text)

        if should_merge_suggestions:
            QuestionService.__merge_suggestions(
                existing_question=existing_question,
                equivalent_suggestion=equivalent_suggestion,
                chosen_question_id=chosen_question_id,
                answer_text=answer_text,
                user=user,
            )

            existing_question.equivalent_questions.add(
                *equivalent_suggestion.equivalent_questions.all()
            )

            existing_question.equivalent_suggestions.add(
                *equivalent_suggestion.equivalent_suggestions.all()
            )

            equivalent_suggestion.equivalent_questions.clear()
            equivalent_suggestion.equivalent_suggestions.clear()

            add_equivalent_question(
                default_question=existing_question,
                equivalent_question=equivalent_suggestion,
            )

        existing_question.equivalent_suggestions.remove(equivalent_suggestion)

    @staticmethod
    def remove_suggestions_alert(organization: Organization):
        alerts = Alert.objects.filter(
            receiver__organization=organization,
            type=ALERT_TYPES['LIBRARY_ENTRY_SUGGESTIONS'],
        )
        suggestion_alerts = LibraryEntrySuggestionsAlert.objects.filter(
            alert__in=alerts
        )
        suggestion_alerts.delete()
        alerts.delete()

import logging
import re

import graphene
from django.db.models import Q
from graphene_django.types import DjangoObjectType

from laika.types import (
    BaseResponseType,
    BulkUploadType,
    PaginationInputType,
    PaginationResponseType,
)
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.paginator import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, get_paginated_result
from library.constants import TASK_COMPLETED_STATUS, TASK_ERROR_STATUS
from library.models import LibraryEntry, LibraryTask, Question, Questionnaire
from library.utils import get_questionnaire_details_filters
from policy.schema import PolicyType
from user.types import UserType

logger = logging.getLogger(__name__)


class AnswerType(graphene.ObjectType):
    _id = graphene.String(name='_id')
    text = graphene.String()
    short_text = graphene.String()


class QuestionType(DjangoObjectType):
    class Meta:
        model = Question

    equivalent_questions = graphene.List(lambda: QuestionType)

    def resolve_equivalent_questions(self, info):
        query_filter = Q(questionnaires__completed=True) | Q(
            questionnaires__isnull=True
        )
        if self.default:
            return self.equivalent_questions.filter(query_filter).order_by(
                '-library_entry__updated_at'
            )
        else:
            try:
                default_question = Question.objects.get(
                    default=True, equivalent_questions__id=self.id
                )
                query_filter &= Q(
                    id__in=default_question.equivalent_questions.exclude(id=self.id)
                )
                other_questions = Question.objects.filter(query_filter).order_by(
                    '-library_entry__updated_at'
                )
                return [default_question] + list(other_questions)
            except Exception as e:
                logger.error(
                    'Error trying to resolve equivalent question'
                    f' question-id: {self.id} {e}'
                )
                return []


class QuestionResponseType(graphene.ObjectType):
    data = graphene.List(QuestionType)
    pagination = graphene.Field(PaginationResponseType, required=False)


class QuestionnaireDetailsFilterType(graphene.InputObjectType):
    search = graphene.String()
    status = graphene.List(graphene.String)
    fetch = graphene.List(graphene.String)
    assignee = graphene.List(graphene.String)


class QuestionnaireProgressType(graphene.ObjectType):
    id = graphene.String(name='id')
    percent = graphene.Float()
    completed = graphene.Int()
    total = graphene.Int()


class QuestionnaireType(DjangoObjectType):
    class Meta:
        model = Questionnaire

    questions = graphene.Field(
        QuestionResponseType,
        filters=graphene.Argument(QuestionnaireDetailsFilterType),
        pagination=graphene.Argument(PaginationInputType, required=False),
    )
    progress = graphene.Field(QuestionnaireProgressType)

    def resolve_questions(self, info, **kwargs):
        def _sort(question: Question) -> tuple:
            try:
                metadata = question.metadata
                address = metadata.get('questionAddress').split('!')[1]
                match = re.match(r"([a-zA-Z]+)([0-9]+)", address)
                if match:
                    column = match.group(1)
                    row = int(match.group(2))
                    return (
                        metadata.get('sheet').get('position'),
                        len(column),
                        column,
                        row,
                    )
                return ()
            except Exception as e:
                logger.exception(
                    f'Error when sorting Questionnaire Questions. Error: {e}'
                )
                return ()

        filters_data = kwargs.get('filters', {})
        filters = get_questionnaire_details_filters(filters_data)
        questions = self.questions.filter(filters)
        questions_with_metadata = [q for q in questions if q.metadata]
        questions_without_metadata = [q for q in questions if not q.metadata]

        pagination = kwargs.get('pagination')
        not_paginated_result = (
            sorted(questions_with_metadata, key=_sort) + questions_without_metadata
        )

        if not pagination:
            return QuestionResponseType(data=not_paginated_result)

        page = pagination.page if pagination else DEFAULT_PAGE
        page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE

        paginated_result = get_paginated_result(not_paginated_result, page_size, page)

        return QuestionResponseType(
            data=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    def resolve_progress(self, info, **kwargs):
        questions_completed = self.questions.filter(completed=True).count()
        questions_total = self.questions.count()
        percent = (
            100.0 * questions_completed / questions_total if questions_total > 0 else 0
        )
        return QuestionnaireProgressType(
            id=self.id,
            percent=percent,
            completed=questions_completed,
            total=questions_total,
        )


class LibraryEntryType(DjangoObjectType):
    class Meta:
        model = LibraryEntry
        fields = (
            'id',
            'category',
            'display_id',
            'updated_by',
            'created_at',
            'updated_at',
        )

    category = graphene.String()
    display_id = graphene.String()
    updated_by_details = graphene.Field(UserType)
    question = graphene.Field(QuestionType)
    aliases = graphene.List(graphene.String)
    answer = graphene.Field(AnswerType)
    organization = graphene.String()

    def resolve_display_id(self, info):
        return f'Q-{self.display_id}'

    def resolve_updated_by_details(self, info):
        return self.updated_by

    def resolve_question(self, info):
        return self.question

    def resolve_aliases(self, info):
        return self.question.equivalent_questions.all()

    def resolve_answer(self, info):
        return AnswerType(
            _id=self.id, text=self.answer_text, short_text=self.short_answer_text
        )

    def resolve_category(self, info):
        return self.category

    def resolve_organization(self, info):
        return self.organization.name


class LibraryEntriesResponseType(graphene.ObjectType):
    entries = graphene.List(LibraryEntryType)
    page = graphene.Int()
    total_count = graphene.Int()


class SearchLibraryMatchesInput(graphene.InputObjectType):
    questions = graphene.List(graphene.String)
    threshold = graphene.Float()


class SearchResultType(graphene.ObjectType):
    _id = graphene.String(name='_id')
    match = graphene.Field(LibraryEntryType)


class LibraryMatchResponseType(BaseResponseType):
    data = graphene.List(SearchResultType)


class QuestionnaireResponseType(graphene.ObjectType):
    questionnaires = graphene.List(QuestionnaireType)
    pagination = graphene.Field(PaginationResponseType, required=False)
    api_token = graphene.String()


class NewQuestionnaireResponseType(graphene.ObjectType):
    id = graphene.ID()
    name = graphene.String()
    organization = graphene.String()


class QuestionnaireFilterInputType(graphene.InputObjectType):
    name = graphene.String()
    completed = graphene.Boolean(required=True)


class QuestionnaireDetailsResponseType(graphene.ObjectType):
    questionnaire = graphene.Field(QuestionnaireType)


class UnionSearchResponseType(graphene.Union):
    class Meta:
        types = (QuestionType, PolicyType)


class LibrarySearchResponseType(graphene.ObjectType):
    id = graphene.String(name='id')
    type = graphene.String()
    response = graphene.Field(UnionSearchResponseType)


class FetchDdqAnswersResponseType(graphene.ObjectType):
    updated = graphene.List(QuestionType)


class LibraryQuestionsResponseType(graphene.ObjectType):
    has_library_questions = graphene.Boolean()
    library_questions = graphene.List(QuestionType)
    pagination = graphene.Field(PaginationResponseType, required=False)


class LibraryQuestionsFilterInputType(graphene.InputObjectType):
    text = graphene.String()


class FailedRowType(graphene.ObjectType):
    type = graphene.String()
    addresses = graphene.List(graphene.String)


class LibraryBulkUploadType(BulkUploadType):
    success_rows = graphene.List(QuestionType, default_value=[])
    failed_rows = graphene.List(FailedRowType, default_value=[])


class QuestionsWithSuggestionsResponseType(graphene.ObjectType):
    has_suggestions = graphene.Boolean()
    suggestions = graphene.List(QuestionType)


class LibraryTaskType(DjangoObjectType):
    class Meta:
        model = LibraryTask

    finished = graphene.Boolean()

    def resolve_finished(self, info):
        return self.status in [TASK_COMPLETED_STATUS, TASK_ERROR_STATUS]


class LibraryTaskResponseType(graphene.ObjectType):
    library_tasks = graphene.List(LibraryTaskType)

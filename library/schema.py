import ast

import graphene
from django.db.models import Q

from laika.auth import login_required
from laika.decorators import laika_service
from laika.types import FiltersType, OrderInputType, PaginationInputType
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.order_by import get_order_queries
from laika.utils.paginator import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, get_paginated_result
from library.constants import FetchType
from library.fetch import Fetch
from library.models import LibraryEntry, LibraryTask, Questionnaire
from library.mutations import (
    AddDocumentsQuestionnaireDataroom,
    AddEquivalentQuestion,
    BulkLibraryUpload,
    BulkUpdateQuestionnaireStatus,
    CreateQuestionnaireEntry,
    CreateQuestionnaireQuestions,
    DeleteLibraryQuestion,
    DeleteQuestionnaire,
    DeleteQuestionnaireQuestions,
    RemoveEquivalentQuestion,
    ResolveEquivalentSuggestion,
    UpdateLibraryQuestion,
    UpdateLibraryQuestionStatus,
    UpdateQuestionAnswer,
    UpdateQuestionAssignedUser,
    UseQuestionAnswer,
)
from library.services.question import QuestionService
from library.types import (
    FetchDdqAnswersResponseType,
    LibraryEntriesResponseType,
    LibraryMatchResponseType,
    LibraryQuestionsFilterInputType,
    LibraryQuestionsResponseType,
    LibrarySearchResponseType,
    LibraryTaskResponseType,
    QuestionnaireDetailsFilterType,
    QuestionnaireDetailsResponseType,
    QuestionnaireFilterInputType,
    QuestionnaireResponseType,
    QuestionsWithSuggestionsResponseType,
    SearchLibraryMatchesInput,
    SearchResultType,
)
from library.utils import (
    get_organization_question_filters,
    notify_library_entry_answer_modification,
    search_questions,
)
from organization.utils.api_token_generator import (
    delete_excel_token,
    generate_api_token,
)
from search.indexing.policy_index import policy_search_index
from search.indexing.question_index import question_search_index
from search.search import search

SEARCH_THRESHOLD = 0.3
MAX_RECORDS_COUNT = 20


class Mutation(graphene.ObjectType):
    add_equivalent_question = AddEquivalentQuestion.Field()
    add_documents_questionnaire_dataroom = AddDocumentsQuestionnaireDataroom.Field()
    create_questionnaire_entry = CreateQuestionnaireEntry.Field()
    bulk_library_upload = BulkLibraryUpload.Field()
    bulk_update_questionnaire_status = BulkUpdateQuestionnaireStatus.Field()
    delete_questionnaire = DeleteQuestionnaire.Field()
    create_questionnaire_questions = CreateQuestionnaireQuestions.Field()
    delete_questionnaire_questions = DeleteQuestionnaireQuestions.Field()
    remove_equivalent_question = RemoveEquivalentQuestion.Field()
    update_question_assigned_user = UpdateQuestionAssignedUser.Field()
    update_library_question_status = UpdateLibraryQuestionStatus.Field()
    update_question_answer = UpdateQuestionAnswer.Field()
    use_question_answer = UseQuestionAnswer.Field()
    update_library_question = UpdateLibraryQuestion.Field()
    delete_library_question = DeleteLibraryQuestion.Field()
    resolve_equivalent_suggestion = ResolveEquivalentSuggestion.Field()


class Query(object):
    library_entries = graphene.Field(
        LibraryEntriesResponseType,
        size=graphene.Int(default_value=5),
        page=graphene.Int(default_value=1),
        search_criteria=graphene.String(),
        filters=graphene.List(graphene.String, default_value=[]),
    )
    search_library_matches = graphene.Field(
        LibraryMatchResponseType, input=graphene.Argument(SearchLibraryMatchesInput)
    )
    questionnaires = graphene.Field(
        QuestionnaireResponseType,
        filter=graphene.Argument(QuestionnaireFilterInputType, required=False),
        pagination=graphene.Argument(PaginationInputType, required=False),
        order_by=graphene.Argument(graphene.List(OrderInputType)),
        generate_token=graphene.Boolean(default_value=False, required=False),
    )
    questionnaire_details = graphene.Field(
        QuestionnaireDetailsResponseType,
        id=graphene.String(required=True),
        pagination=graphene.Argument(PaginationInputType, required=False),
        filters=graphene.Argument(QuestionnaireDetailsFilterType, required=False),
    )
    library_search = graphene.List(
        LibrarySearchResponseType,
        search_criteria=graphene.String(),
        filters=graphene.List(graphene.String),
    )
    question_filters = graphene.List(
        FiltersType,
        id=graphene.String(required=True),
    )
    fetch_ddq_answers = graphene.Field(
        FetchDdqAnswersResponseType,
        id=graphene.String(required=True),
        fetch_type=graphene.String(default_value=FetchType.EXACT.value),
    )
    library_questions = graphene.Field(
        LibraryQuestionsResponseType,
        filter=graphene.Argument(LibraryQuestionsFilterInputType, required=False),
        pagination=graphene.Argument(PaginationInputType, required=False),
        order_by=graphene.Argument(graphene.List(OrderInputType)),
    )
    questions_with_suggestions = graphene.Field(QuestionsWithSuggestionsResponseType)
    library_tasks = graphene.Field(LibraryTaskResponseType)

    @laika_service(
        atomic=False,
        permission='library.view_libraryentry',
        exception_msg='Failed to retrieve library entries',
    )
    def resolve_library_entries(self, info, **kwargs):
        organization = info.context.user.organization
        filters = kwargs.get('filters')
        filter_params = {'organization': organization}

        for f in filters:
            filter_params.update(ast.literal_eval(f))

        search_criteria = kwargs.get('search_criteria')

        entries = LibraryEntry.objects.filter(
            Q(question__questionnaires__completed=True)
            | Q(question__questionnaires__isnull=True)
            & Q(question__isnull=False)
            & Q(question__deleted_at__isnull=True),
            Q(question__default=True),
            **filter_params,
        ).order_by('-updated_at')

        if search_criteria:
            entries = search_questions(organization, search_criteria, entries)

        size = kwargs.get('size')
        page = kwargs.get('page')
        paginated_result = get_paginated_result(entries, size, page)

        return LibraryEntriesResponseType(
            entries=paginated_result.get('data'),
            page=paginated_result.get('page'),
            total_count=len(entries),
        )

    @login_required
    def resolve_search_library_matches(self, info, input):
        organization = info.context.user.organization
        threshold = input.threshold if input.threshold else SEARCH_THRESHOLD
        matches = LibraryEntry.objects.raw(
            'SELECT q.input, le.* FROM find_questions('
            '%(questions)s, %(threshold)s, %(organization_id)s) q '
            'LEFT JOIN library_libraryentry le ON le.id = q.library_entry_id '
            'ORDER BY q.question_index ',
            {
                'questions': input.questions,
                'threshold': threshold,
                'organization_id': organization.id,
            },
        )
        data = [search_result(index, match) for index, match in enumerate(matches)]

        return LibraryMatchResponseType(data=data)

    @laika_service(
        permission='library.view_questionnaire',
        exception_msg='Failed to retrieve questionnaires. Please try again',
    )
    def resolve_questionnaires(self, info, **kwargs):
        pagination = kwargs.get('pagination')
        filter_data = kwargs.get('filter')
        order_by = kwargs.get(
            'order_by',
            [
                {'field': 'name', 'order': 'asc'},
            ],
        )
        api_token = None

        page = pagination.page if pagination else DEFAULT_PAGE
        page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE

        if kwargs.get('generate_token'):
            delete_excel_token(info.context.user)
            api_token, _ = generate_api_token(
                user=info.context.user,
                name=f'excel ({info.context.user.email})',
                expiration_days=1,
                usage_type='EXCEL',
            )

        questionnaires = Questionnaire.objects.filter(
            organization=info.context.user.organization,
            completed=filter_data.completed,
            name__icontains=filter_data.name or '',
        ).order_by(*get_order_queries(order_by))
        if not pagination:
            return QuestionnaireResponseType(
                questionnaires=questionnaires, api_token=api_token
            )
        paginated_result = get_paginated_result(questionnaires, page_size, page)

        return QuestionnaireResponseType(
            questionnaires=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
            api_token=api_token,
        )

    @laika_service(
        permission='library.view_questionnaire',
        exception_msg='''
            Failed to retrieve questionnaire detail. Please try again
        ''',
    )
    def resolve_questionnaire_details(self, info, **kwargs):
        questionnaire_id = kwargs.get('id')
        organization = info.context.user.organization
        questionnaire = Questionnaire.objects.get(
            id=questionnaire_id, organization=organization
        )

        return QuestionnaireDetailsResponseType(questionnaire=questionnaire)

    @laika_service(
        permission='library.view_questionnaire',
        exception_msg='Failed to search. Please try again',
    )
    def resolve_library_search(self, info, **kwargs):
        search_criteria = kwargs.get('search_criteria')
        if search_criteria == '':
            return []

        return search(
            search_criteria,
            info.context.user.organization.id,
            [
                policy_search_index.RESOURCE_TYPE,
                question_search_index.RESOURCE_TYPE,
            ],
            records_count=MAX_RECORDS_COUNT,
        )

    @login_required
    def resolve_question_filters(self, info, **kwargs):
        questionnaire_id = kwargs.get('id')
        questionnaire = Questionnaire.objects.get(id=questionnaire_id)
        organization = info.context.user.organization
        filters = get_organization_question_filters(questionnaire, organization)
        return filters

    @laika_service(
        permission='library.view_questionnaire',
        exception_msg='''
            Failed to fetch questions on questionnaire. Please try again
        ''',
    )
    def resolve_fetch_ddq_answers(self, info, **kwargs):
        questionnaire_id = kwargs.get('id')
        organization = info.context.user.organization
        fetch_type = kwargs.get('fetch_type')
        fetch_context = Fetch(fetch_type)
        updated_questions = fetch_context.fetch(questionnaire_id, organization)[0]
        for question in updated_questions:
            notify_library_entry_answer_modification(
                info, question.library_entry, [question]
            )
        return FetchDdqAnswersResponseType(updated=updated_questions)

    @laika_service(
        permission='library.view_libraryentry',
        exception_msg='Failed to retrieve library questions. Please try again',
    )
    def resolve_library_questions(self, info, **kwargs):
        organization = info.context.user.organization
        pagination = kwargs.get('pagination')
        filter_data = kwargs.get('filter').get('text', '')
        order_by = kwargs.get(
            'order_by',
            [
                {'field': 'created_at', 'order': 'descend'},
            ],
        )
        if order_by[0].get('field') == 'updated_at':
            order_by[0]['field'] = 'library_entry__updated_at'

        page = pagination.page if pagination else DEFAULT_PAGE
        page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE

        (
            library_questions,
            has_library_questions,
        ) = QuestionService.get_library_questions(
            organization=organization, order_by=order_by, filter_data=filter_data
        )

        if not pagination:
            return LibraryQuestionsResponseType(
                has_library_questions=has_library_questions,
                library_questions=library_questions,
            )
        paginated_result = get_paginated_result(library_questions, page_size, page)

        return LibraryQuestionsResponseType(
            has_library_questions=has_library_questions,
            library_questions=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @laika_service(
        permission='library.view_libraryentry',
        exception_msg='''
            Failed to retrieve questions with suggestions. Please try again
        ''',
    )
    def resolve_questions_with_suggestions(self, info, **kwargs):
        organization = info.context.user.organization

        suggestions, has_suggestions = QuestionService.get_questions_with_suggestions(
            organization=organization
        )

        return QuestionsWithSuggestionsResponseType(
            has_suggestions=has_suggestions, suggestions=suggestions
        )

    @laika_service(
        permission='library.view_libraryentry',
        exception_msg='''
            Failed to retrieve library tasks. Please try again
        ''',
    )
    def resolve_library_tasks(self, info, **kwargs):
        library_tasks = LibraryTask.objects.filter(
            created_by__organization=info.context.user.organization
        )
        return LibraryTaskResponseType(library_tasks=library_tasks)


def search_result(index, library_entry):
    match = library_entry if library_entry.id else None
    return SearchResultType(_id=index, match=match)

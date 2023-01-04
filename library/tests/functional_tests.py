import io
import json
from collections import OrderedDict
from datetime import datetime
from typing import List, Tuple, Union
from unittest.mock import patch

import django.utils.timezone as timezone
import pytest
from django.core.files import File
from graphene.test import Client

from alert.constants import ALERT_TYPES
from alert.models import Alert
from dataroom.models import Dataroom
from drive.evidence_handler import create_drive_evidence
from drive.models import DriveEvidence
from evidence import constants
from laika.utils.exceptions import ServiceException
from laika.utils.schema_builder.template_builder import SchemaResponse
from laika.utils.schema_builder.types.base_field import RequiredErrorType
from library.constants import (
    NO_RESULT,
    NOT_ASSIGNED_USER_ID,
    NOT_RAN,
    RESULT_FOUND,
    RESULT_FOUND_UPDATED,
    STATUS_COMPLETED,
    STATUS_DRAFT,
    STATUS_IN_PROGRESS,
    STATUS_NO_ANSWER,
    TASK_COMPLETED_STATUS,
)
from library.models import (
    LibraryEntry,
    LibraryEntrySuggestionsAlert,
    LibraryTask,
    Question,
    Questionnaire,
    QuestionnaireAlert,
)
from library.tests.factory import (
    create_library_entry,
    create_question,
    create_question_with_user_assigned,
    create_suggestion_alert,
    create_suggestion_questions,
)
from library.tests.mutations import (
    ADD_DOCUMENTS_QUESTIONNAIRE_DATAROOM,
    ADD_EQUIVALENT_QUESTION,
    BULK_LIBRARY_UPLOAD,
    BULK_UPDATE_QUESTIONNAIRE_STATUS,
    CREATE_NEW_QUESTIONNAIRE,
    CREATE_QUESTIONNAIRE_QUESTIONS,
    DELETE_LIBRARY_QUESTION,
    DELETE_QUESTIONNAIRE,
    DELETE_QUESTIONNAIRE_QUESTIONS,
    REMOVE_EQUIVALENT_QUESTION,
    RESOLVE_EQUIVALENT_SUGGESTION,
    UPDATE_LIBRARY_QUESTION,
    UPDATE_LIBRARY_QUESTION_STATUS,
    UPDATE_QUESTION_ANSWER,
    UPDATE_QUESTION_ASSIGNED_USER,
)
from library.tests.queries import (
    FETCH_EXACT_MATCH,
    FETCH_FUZZY_MATCH,
    GET_LIBRARY_ENTRIES,
    GET_LIBRARY_QUESTIONS,
    GET_LIBRARY_TASKS,
    GET_QUESTIONNAIRE_DETAILS,
    GET_QUESTIONNAIRES,
    GET_QUESTIONNAIRES_FILTERS,
    GET_QUESTIONS_WITH_SUGGESTIONS,
)
from library.tests.utils_tests import multiline_to_singleline
from organization.models import ApiTokenHistory, Organization
from user.models import User
from user.tests import create_user

ANSWER_TEXT = 'Answer Example'
QUESTION_TEXT = 'Question Example'
QUESTION_TEXT_LOWERCASE = 'question example'
QUESTION_TEXT_LOWERCASE_FUZZY = (
    'question example for testing the fuzzy fetch because its important to test stuff.'
)
QUESTION_TEXT_UPPERCASE = 'QUESTION EXAMPLE'
QUESTION_TEXT_UPPERCASE_FUZZY = (
    'QUESTION EXAMPLE FOR TESTING THE FUZZY FETCH BECAUSE ITS IMPORTANT TO TEST STUFF.'
)
QUESTION_TEXT_TABS = 'Question          Example'
QUESTION_TEXT_TABS_FUZZY = (
    'Question        Example     for testing the'
    ' fuzzy       fetch because its important to test stuff.'
)
QUESTION_TEXT_LINE_BREAK = '''
    Question
    Example
'''
QUESTION_TEXT_LINE_BREAK_FUZZY = '''
    Question
    Example
    for
    testing
    the

    fuzzy
    fetch
'''
QUESTION_TEXT_DELETED = 'Question Example Deleted'
QUESTION_TEXT_COMPLETED = 'Question Example Completed'
QUESTIONNAIRE_1_NAME = 'Questionnaire One'
QUESTIONNAIRE_2_NAME = 'Questionnaire Two'
QUESTIONNAIRE_3_NAME = 'Questionnaire Three'


@pytest.fixture()
def user(graphql_organization: Organization) -> User:
    return create_user(graphql_organization, [], 'user+python+test@heylaika.com')


@pytest.fixture()
def library_entry(graphql_organization: Organization) -> LibraryEntry:
    return create_library_entry(graphql_organization)


@pytest.fixture()
def question(graphql_organization: Organization) -> Question:
    return create_question(graphql_organization)


@pytest.fixture()
def non_question_default(
    graphql_organization: Organization,
) -> Question:
    return create_question(graphql_organization, default=False)


@pytest.fixture()
def deleted_question(library_entry: LibraryEntry) -> Question:
    return Question.objects.create(
        default=False,
        library_entry=library_entry,
        text=QUESTION_TEXT_DELETED,
        deleted_at=timezone.now(),
    )


@pytest.fixture()
def completed_question(library_entry: LibraryEntry) -> Question:
    return Question.objects.create(
        default=False,
        library_entry=library_entry,
        text=QUESTION_TEXT_COMPLETED,
        completed=True,
    )


def create_questionnaire(
    name: str,
    organization: Organization,
    with_question: bool,
    question: Union[Question, None],
    completed=False,
) -> Questionnaire:
    questionnaire = Questionnaire.objects.create(
        name=name, organization=organization, completed=completed
    )
    if with_question:
        questionnaire.questions.add(question)
        questionnaire.save()

    return questionnaire


@pytest.fixture()
def questionnaires(
    graphql_organization: Organization, question: Question
) -> List[Questionnaire]:
    entries = [
        (QUESTIONNAIRE_1_NAME, graphql_organization, False, True),
        (QUESTIONNAIRE_2_NAME, graphql_organization, True, False),
        (QUESTIONNAIRE_3_NAME, graphql_organization, True, False),
    ]
    return [
        create_questionnaire(
            name,
            org,
            with_question,
            question,
            completed,
        )
        for (
            name,
            org,
            completed,
            with_question,
        ) in entries
    ]


@pytest.fixture()
def question_metadata():
    return {
        'sheet': {'name': 'Sheet 1', 'position': 0},
        'answerAddresses': ['Sheet1!B1'],
        'questionAddress': 'Sheet1!A1',
    }


def create_question_with_metadata(
    library_entry: LibraryEntry, text: str, metadata: dict
) -> Question:
    return Question.objects.create(
        default=True,
        library_entry=library_entry,
        text=text or QUESTION_TEXT,
        metadata=metadata,
    )


@pytest.fixture()
def suggestion_questions(
    graphql_organization: Organization,
) -> Tuple[Question, Question]:
    return create_suggestion_questions(graphql_organization)


@pytest.fixture()
def dataroom(graphql_organization: Organization) -> Dataroom:
    return Dataroom.objects.create(
        organization=graphql_organization, name=f'{QUESTIONNAIRE_1_NAME} Dataroom'
    )


@pytest.fixture()
def drive_evidence(
    graphql_organization: Organization,
    graphql_user: User,
) -> DriveEvidence:
    template_content = 'My test'
    template_file = File(name='test', file=io.BytesIO(template_content.encode()))
    template = create_drive_evidence(
        graphql_organization, template_file, graphql_user, constants.LAIKA_PAPER
    )
    drive_evidence = DriveEvidence.objects.get(evidence=template)
    drive_evidence.is_template = True
    drive_evidence.save()

    return drive_evidence


def create_questions_to_filter(
    graphql_organization: Organization, user: User
) -> List[Question]:
    # id-2
    q1 = create_question_with_user_assigned(
        graphql_organization,
        question_text=f'{QUESTION_TEXT} 2',
        answer_text=f'{ANSWER_TEXT} 2',
        user_assigned=user,
        completed=True,
    )
    # id-3
    q2 = create_question(
        graphql_organization,
        question_text=f'{QUESTION_TEXT} 3 to search',
        answer_text=f'{ANSWER_TEXT} 3',
        default=False,
        fetch_status=NO_RESULT,
    )
    # id-4
    q3 = create_question_with_user_assigned(
        graphql_organization,
        question_text=f'{QUESTION_TEXT} 4',
        answer_text=f'{ANSWER_TEXT} 4',
        user_assigned=user,
        completed=False,
    )
    # id-5
    q4 = create_question(
        graphql_organization,
        question_text=f'{QUESTION_TEXT} 5',
        answer_text=f'{ANSWER_TEXT} 5 to search',
        default=False,
        fetch_status=RESULT_FOUND,
    )
    q4.completed = True
    q4.save()
    # id-6
    q5 = create_question(
        graphql_organization,
        question_text=f'{QUESTION_TEXT} 5',
        answer_text='',
        default=False,
    )
    return [q1, q2, q3, q4, q5]


@pytest.mark.functional(permissions=['library.view_libraryentry'])
def test_get_library_entries_with_soft_deleted_questions(
    graphql_client: Client,
    graphql_organization: Organization,
    question: Question,
):
    question.deleted_at = datetime.now(timezone.utc)
    question.save()
    response = graphql_client.execute(
        GET_LIBRARY_ENTRIES,
        variables={'filter': [], 'page': 1, 'searchCriteria': '', 'size': 5},
    )
    data = response['data']['libraryEntries']['entries']
    assert len(data) == 0


@pytest.mark.functional(permissions=['library.view_libraryentry'])
def test_get_library_entries_completed_questionnaires(
    graphql_client: Client,
    graphql_organization: Organization,
    question: Question,
    non_question_default: Question,
):
    questionnaire = create_questionnaire(
        QUESTIONNAIRE_1_NAME, graphql_organization, True, question, True
    )
    questionnaire.questions.add(non_question_default)
    response = graphql_client.execute(
        GET_LIBRARY_ENTRIES,
        variables={'filter': [], 'page': 1, 'searchCriteria': '', 'size': 5},
    )
    data = response['data']['libraryEntries']['entries']

    assert 1 == len(data)
    assert question.id == int(data[0].get('id'))


@pytest.mark.functional(permissions=['library.view_libraryentry'])
def test_get_library_entries_completed_questionnaires_non_related_question(
    graphql_client: Client,
    graphql_organization: Organization,
    question: Question,
    library_entry: LibraryEntry,
):
    create_questionnaire(
        QUESTIONNAIRE_1_NAME, graphql_organization, True, question, True
    )
    create_question_with_metadata(library_entry, 'Text', {})
    response = graphql_client.execute(
        GET_LIBRARY_ENTRIES,
        variables={'filter': [], 'page': 1, 'searchCriteria': '', 'size': 5},
    )
    data = response['data']['libraryEntries']['entries']

    assert len(data) == 2


@pytest.mark.functional(permissions=['library.view_libraryentry'])
def test_get_library_entries_completed_uncompleted_questionnaires(
    graphql_client: Client,
    graphql_organization: Organization,
    question: Question,
):
    create_questionnaire(
        QUESTIONNAIRE_1_NAME, graphql_organization, True, question, True
    )
    create_questionnaire(
        QUESTIONNAIRE_2_NAME, graphql_organization, True, question, False
    )
    response = graphql_client.execute(
        GET_LIBRARY_ENTRIES,
        variables={'filter': [], 'page': 1, 'searchCriteria': '', 'size': 5},
    )
    data = response['data']['libraryEntries']['entries']

    assert len(data) == 1


@pytest.mark.functional(permissions=['library.view_libraryentry'])
def test_get_library_entries_uncompleted_questionnaires(
    graphql_client: Client, graphql_organization: Organization, question: Question
):
    create_questionnaire(
        QUESTIONNAIRE_1_NAME, graphql_organization, True, question, False
    )
    create_questionnaire(
        QUESTIONNAIRE_2_NAME, graphql_organization, True, question, False
    )
    response = graphql_client.execute(
        GET_LIBRARY_ENTRIES,
        variables={'filter': [], 'page': 1, 'searchCriteria': '', 'size': 5},
    )
    data = response['data']['libraryEntries']['entries']

    assert len(data) == 0


@pytest.mark.functional(permissions=['library.view_libraryentry'])
def test_get_library_entries_uncompleted_questionnaires_non_related_question(
    graphql_client: Client,
    graphql_organization: Organization,
    question: Question,
    library_entry: LibraryEntry,
):
    create_questionnaire(
        QUESTIONNAIRE_1_NAME, graphql_organization, True, question, False
    )
    create_questionnaire(
        QUESTIONNAIRE_2_NAME, graphql_organization, True, question, False
    )
    create_question_with_metadata(library_entry, 'Text', {})
    response = graphql_client.execute(
        GET_LIBRARY_ENTRIES,
        variables={'filter': [], 'page': 1, 'searchCriteria': '', 'size': 5},
    )
    data = response['data']['libraryEntries']['entries']

    assert len(data) == 1


@pytest.mark.functional(permissions=['library.view_questionnaire'])
@pytest.mark.parametrize(
    'count_completed_name', [[1, False, None], [2, True, None], [1, True, 'Three']]
)
def test_get_in_progress_questionnaires(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    count_completed_name,
):
    count, completed, name = count_completed_name
    response = graphql_client.execute(
        GET_QUESTIONNAIRES,
        variables={
            'filter': {'completed': completed, 'name': name},
            'pagination': dict(page=1, pageSize=10),
        },
    )
    data = response['data']['questionnaires']['questionnaires']

    assert len(data) == count


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_get_in_progress_questionnaires_order_by(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    response = graphql_client.execute(
        GET_QUESTIONNAIRES,
        variables={
            'filter': {'completed': True},
            'orderBy': [{'field': 'name', 'order': 'desc'}],
            'pagination': dict(page=1, pageSize=10),
        },
    )
    data = response['data']['questionnaires']['questionnaires']

    assert data[0].get('name') == QUESTIONNAIRE_3_NAME


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_get_questionnaire_with_api_token(
    graphql_client: Client,
    graphql_organization: Organization,
):
    response = graphql_client.execute(
        GET_QUESTIONNAIRES,
        variables={
            'generateToken': True,
            'filter': {'completed': False},
            'pagination': dict(page=1, pageSize=10),
        },
    )
    token = response['data']['questionnaires']['apiToken']

    assert token is not None
    assert ApiTokenHistory.all_objects.filter(usage_type='EXCEL').count() == 1


@pytest.mark.functional(permissions=['library.change_questionnaire'])
def test_update_questionnaire_status(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire_ids = []
    for questionnaire in questionnaires:
        questionnaire_ids.append(questionnaire.id)

    response = graphql_client.execute(
        BULK_UPDATE_QUESTIONNAIRE_STATUS,
        variables={
            'input': dict(
                ids=questionnaire_ids,
                status=STATUS_COMPLETED,
            )
        },
    )

    assert len(response['data']['bulkUpdateQuestionnaireStatus']['updated']) == 3

    updated_questionnaires = Questionnaire.objects.filter(id__in=questionnaire_ids)
    for updated_questionnaire in updated_questionnaires:
        assert updated_questionnaire.completed is True


@pytest.mark.functional(permissions=['library.change_questionnaire'])
def test_delete_questionnaire_and_questions(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire_ids = []
    for questionnaire in questionnaires:
        questionnaire_ids.append(questionnaire.id)

    assert LibraryEntry.objects.all().count() == 1

    response = graphql_client.execute(
        DELETE_QUESTIONNAIRE,
        variables={'input': dict(ids=questionnaire_ids, deleteAllQuestions=True)},
    )
    assert len(response['data']['deleteQuestionnaire']['deleted']) == 3

    deleted_questionnaires = Questionnaire.objects.filter(id__in=questionnaire_ids)
    assert deleted_questionnaires.count() == 0
    assert Question.objects.all().count() == 0
    assert LibraryEntry.objects.all().count() == 0


@pytest.mark.functional(
    permissions=['library.change_questionnaire', 'library.change_question']
)
def test_delete_questionnaire_with_alerts(
    graphql_client: Client,
    question: Question,
    questionnaires: List[Questionnaire],
    user: User,
):
    questionnaire = questionnaires[0]
    graphql_client.execute(
        UPDATE_QUESTION_ASSIGNED_USER,
        variables={
            'input': {
                'questionId': question.id,
                'questionnaireId': questionnaire.id,
                'userAssignedEmail': user.email,
            },
        },
    )

    alerts = QuestionnaireAlert.objects.filter(questionnaire_id=questionnaire.id)

    assert alerts.count() == 1

    response = graphql_client.execute(
        DELETE_QUESTIONNAIRE,
        variables={'input': dict(ids=[questionnaire.id], deleteAllQuestions=True)},
    )
    assert len(response['data']['deleteQuestionnaire']['deleted']) == 1

    new_alerts = QuestionnaireAlert.objects.filter(questionnaire_id=questionnaire.id)

    assert new_alerts.count() == 0


@pytest.mark.functional(permissions=['library.change_questionnaire'])
def test_delete_only_questionnaire(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire_ids = []
    for questionnaire in questionnaires:
        questionnaire_ids.append(questionnaire.id)

    questions_len = Question.objects.all().count()

    response = graphql_client.execute(
        DELETE_QUESTIONNAIRE,
        variables={'input': dict(ids=questionnaire_ids, deleteAllQuestions=False)},
    )
    assert len(response['data']['deleteQuestionnaire']['deleted']) == 3

    deleted_questionnaires = Questionnaire.objects.filter(id__in=questionnaire_ids)
    assert deleted_questionnaires.count() == 0
    assert Question.objects.all().count() == questions_len
    assert LibraryEntry.objects.all().count() == 1


@pytest.mark.functional(permissions=['library.change_questionnaire'])
def test_delete_questionnaire_with_dataroom(
    graphql_client: Client,
    questionnaires: List[Questionnaire],
    dataroom: Dataroom,
):
    questionnaire = questionnaires[0]
    questionnaire.dataroom = dataroom
    questionnaire.save()

    questionnaire_ids = [questionnaire.id]

    response = graphql_client.execute(
        DELETE_QUESTIONNAIRE,
        variables={'input': dict(ids=questionnaire_ids, deleteAllQuestions=False)},
    )
    assert len(response['data']['deleteQuestionnaire']['deleted']) == 1

    deleted_questionnaires = Questionnaire.objects.filter(id__in=questionnaire_ids)
    assert deleted_questionnaires.count() == 0

    soft_deleted_dataroom = Dataroom.objects.get(id=dataroom.id)
    assert soft_deleted_dataroom.is_soft_deleted is True


@pytest.mark.functional(permissions=['library.change_questionnaire'])
def test_delete_questionnaire_failed(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire_name = 'Questionnaire Name'
    new_questionnaire = create_questionnaire(
        questionnaire_name, graphql_organization, False, None
    )
    id = new_questionnaire.id
    new_questionnaire.delete()

    response = graphql_client.execute(
        DELETE_QUESTIONNAIRE,
        variables={'input': dict(ids=[id], deleteAllQuestions=True)},
    )

    assert response['errors'][0]['message'] == 'Invalid questionnaire(s) to delete'


@pytest.mark.functional(permissions=['library.add_questionnaire'])
def test_add_new_questionnaire(
    graphql_client: Client, graphql_organization: Organization
):
    questionnaire_name = 'Questionnaire Test'
    params = {'name': questionnaire_name}
    result = graphql_client.execute(CREATE_NEW_QUESTIONNAIRE, variables=params)
    assert result.get('data').get('createQuestionnaireEntry') is not None


@pytest.mark.functional(permissions=['library.add_questionnaire'])
def test_add_new_questionnaire_repeated(
    graphql_client: Client, graphql_organization: Organization
):
    questionnaire_name = 'Questionnaire Name'
    create_questionnaire(questionnaire_name, graphql_organization, False, None)
    params = {'name': questionnaire_name}
    result = graphql_client.execute(CREATE_NEW_QUESTIONNAIRE, variables=params)

    formated_response = multiline_to_singleline(result['errors'][0]['message'])
    expected_response = multiline_to_singleline(
        """
        This questionnaire name is already in use.
        Please enter a unique name.
        """
    )

    assert formated_response == expected_response


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_get_questionnaire_details(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire_id = questionnaires[0].id

    response = graphql_client.execute(
        GET_QUESTIONNAIRE_DETAILS,
        variables={
            'id': questionnaire_id,
        },
    )
    questionnaire_response = response['data']['questionnaireDetails']['questionnaire']

    questionnaire_question = questionnaire_response['questions']['data'][0]

    assert questionnaire_response['name'] == QUESTIONNAIRE_1_NAME
    assert len(questionnaire_response['questions']['data']) == 1
    assert questionnaire_question['text'] == QUESTION_TEXT
    assert questionnaire_question['libraryEntry']['answer']['text'] == ANSWER_TEXT


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_get_questionnaire_details_sorted_questions_same_sheet(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire = questionnaires[0]
    questionnaire_id = questionnaire.id
    # id-2
    q1 = create_question_with_metadata(
        create_library_entry(graphql_organization),
        QUESTION_TEXT + '1',
        {
            "sheet": {"name": "Sheet1", "position": 0},
            "answerAddress": "Sheet1!B50",
            "questionAddress": "Sheet1!A50",
        },
    )
    # id-3
    q2 = create_question_with_metadata(
        create_library_entry(graphql_organization),
        QUESTION_TEXT + '2',
        {
            "sheet": {"name": "Sheet1", "position": 0},
            "answerAddress": "Sheet1!B14",
            "questionAddress": "Sheet1!A14",
        },
    )
    # id-4
    q3 = create_question_with_metadata(
        create_library_entry(graphql_organization),
        QUESTION_TEXT + '3',
        {
            "sheet": {"name": "Sheet1", "position": 0},
            "answerAddress": "Sheet1!C4",
            "questionAddress": "Sheet1!B4",
        },
    )
    # id-5
    q4 = create_question_with_metadata(
        create_library_entry(graphql_organization),
        QUESTION_TEXT + '4',
        {
            "sheet": {"name": "Sheet1", "position": 0},
            "answerAddress": "Sheet1!B2",
            "questionAddress": "Sheet1!A2",
        },
    )
    questionnaire.questions.add(*[q1, q2, q3, q4])

    response = graphql_client.execute(
        GET_QUESTIONNAIRE_DETAILS,
        variables={
            'id': questionnaire_id,
        },
    )
    questionnaire_response = response['data']['questionnaireDetails']['questionnaire']

    questionnaire_questions = questionnaire_response['questions']['data']
    assert len(questionnaire_questions) == 5
    assert questionnaire_questions[0]['id'] == '5'
    assert questionnaire_questions[1]['id'] == '3'
    assert questionnaire_questions[2]['id'] == '2'
    assert questionnaire_questions[3]['id'] == '4'
    assert questionnaire_questions[4]['id'] == '1'


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_get_questionnaire_details_sorted_questions_different_sheet(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire = questionnaires[0]
    questionnaire_id = questionnaire.id
    # id-2
    q1 = create_question_with_metadata(
        create_library_entry(graphql_organization),
        QUESTION_TEXT + '1',
        {
            "sheet": {"name": "Sheet1", "position": 50},
            "answerAddress": "Sheet1!B10",
            "questionAddress": "Sheet1!A10",
        },
    )
    # id-3
    q2 = create_question_with_metadata(
        create_library_entry(graphql_organization),
        QUESTION_TEXT + '2',
        {
            "sheet": {"name": "Sheet1", "position": 50},
            "answerAddress": "Sheet1!B1",
            "questionAddress": "Sheet1!A1",
        },
    )
    # id-4
    q3 = create_question_with_metadata(
        create_library_entry(graphql_organization),
        QUESTION_TEXT + '3',
        {
            "sheet": {"name": "Sheet1", "position": 5},
            "answerAddress": "Sheet1!C4",
            "questionAddress": "Sheet1!B4",
        },
    )
    # id-5
    q4 = create_question_with_metadata(
        create_library_entry(graphql_organization),
        QUESTION_TEXT + '4',
        {
            "sheet": {"name": "Sheet1", "position": 0},
            "answerAddress": "Sheet1!C4",
            "questionAddress": "Sheet1!B4",
        },
    )
    # id-6
    q5 = create_question_with_metadata(
        create_library_entry(graphql_organization),
        QUESTION_TEXT + '5',
        {
            "sheet": {"name": "Sheet1", "position": 5},
            "answerAddress": "Sheet1!B20",
            "questionAddress": "Sheet1!A20",
        },
    )
    # id-7
    q6 = create_question_with_metadata(
        create_library_entry(graphql_organization),
        QUESTION_TEXT + '6',
        {
            "sheet": {"name": "Sheet1", "position": 0},
            "answerAddress": "Sheet1!B2",
            "questionAddress": "Sheet1!A2",
        },
    )
    # id-8
    q7 = create_question_with_metadata(
        create_library_entry(graphql_organization),
        QUESTION_TEXT + '7',
        {
            "sheet": {"name": "Sheet1", "position": 0},
            "answerAddress": "Sheet1!BB2",
            "questionAddress": "Sheet1!AA2",
        },
    )
    questionnaire.questions.add(*[q1, q2, q3, q4, q5, q6, q7])

    response = graphql_client.execute(
        GET_QUESTIONNAIRE_DETAILS,
        variables={
            'id': questionnaire_id,
        },
    )
    questionnaire_response = response['data']['questionnaireDetails']['questionnaire']

    questionnaire_questions = questionnaire_response['questions']['data']
    assert len(questionnaire_questions) == 8
    assert questionnaire_questions[0]['id'] == '7'
    assert questionnaire_questions[1]['id'] == '5'
    assert questionnaire_questions[2]['id'] == '8'
    assert questionnaire_questions[3]['id'] == '6'
    assert questionnaire_questions[4]['id'] == '4'
    assert questionnaire_questions[5]['id'] == '3'
    assert questionnaire_questions[6]['id'] == '2'
    assert questionnaire_questions[7]['id'] == '1'


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_get_questionnaires_filters_for_questions(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    user: User,
):
    questionnaire = questionnaires[0]
    questionnaire_id = questionnaire.id
    create_user(graphql_organization, [], 'new+user+python+test@heylaika.com')

    questions_to_filter = create_questions_to_filter(graphql_organization, user)

    questionnaire.questions.add(*questions_to_filter)

    response = graphql_client.execute(
        GET_QUESTIONNAIRES_FILTERS, variables={'id': questionnaire_id}
    )
    users_assigned = response['data']['questionFilters'][2]

    assert len(users_assigned['items']) == 1


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_get_questionnaire_details_filtered_by_no_answer_status(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    user: User,
):
    questionnaire = questionnaires[0]
    questionnaire_id = questionnaire.id
    questions_to_filter = create_questions_to_filter(graphql_organization, user)

    questionnaire.questions.add(*questions_to_filter)

    response = graphql_client.execute(
        GET_QUESTIONNAIRE_DETAILS,
        variables={'id': questionnaire_id, 'filters': dict(status=[STATUS_NO_ANSWER])},
    )
    questionnaire_response = response['data']['questionnaireDetails']['questionnaire']

    assert len(questionnaire_response['questions']['data']) == 1


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_get_questionnaire_details_filtered_by_draft_status(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    user: User,
):
    questionnaire = questionnaires[0]
    questionnaire_id = questionnaire.id
    questions_to_filter = create_questions_to_filter(graphql_organization, user)

    questionnaire.questions.add(*questions_to_filter)

    response = graphql_client.execute(
        GET_QUESTIONNAIRE_DETAILS,
        variables={'id': questionnaire_id, 'filters': dict(status=[STATUS_DRAFT])},
    )
    questionnaire_response = response['data']['questionnaireDetails']['questionnaire']

    assert len(questionnaire_response['questions']['data']) == 3


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_get_questionnaire_details_filtered_by_fetch_status_fetched(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    user: User,
):
    questionnaire = questionnaires[0]
    questionnaire_id = questionnaire.id
    questions_to_filter = create_questions_to_filter(graphql_organization, user)

    questionnaire.questions.add(*questions_to_filter)

    response = graphql_client.execute(
        GET_QUESTIONNAIRE_DETAILS,
        variables={'id': questionnaire_id, 'filters': dict(fetch=['fetched'])},
    )

    questionnaire_response = response['data']['questionnaireDetails']['questionnaire']

    assert len(questionnaire_response['questions']['data']) == 1


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_get_questionnaire_details_filtered_by_fetch_status_not_fetched(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    user: User,
):
    questionnaire = questionnaires[0]
    questionnaire_id = questionnaire.id
    questions_to_filter = create_questions_to_filter(graphql_organization, user)

    questionnaire.questions.add(*questions_to_filter)

    response = graphql_client.execute(
        GET_QUESTIONNAIRE_DETAILS,
        variables={'id': questionnaire_id, 'filters': dict(fetch=['not_fetched'])},
    )

    questionnaire_response = response['data']['questionnaireDetails']['questionnaire']

    assert len(questionnaire_response['questions']['data']) == 5


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_get_questionnaire_details_filtered_by_user(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    user: User,
):
    questionnaire = questionnaires[0]
    questionnaire_id = questionnaire.id
    questions_to_filter = create_questions_to_filter(graphql_organization, user)

    questionnaire.questions.add(*questions_to_filter)

    response = graphql_client.execute(
        GET_QUESTIONNAIRE_DETAILS,
        variables={'id': questionnaire_id, 'filters': dict(assignee=[str(user.id)])},
    )
    questionnaire_response = response['data']['questionnaireDetails']['questionnaire']

    assert len(questionnaire_response['questions']['data']) == 2


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_get_questionnaire_details_filtered_by_not_assigned_user(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    user: User,
):
    questionnaire = questionnaires[0]
    questionnaire_id = questionnaire.id
    questions_to_filter = create_questions_to_filter(graphql_organization, user)

    questionnaire.questions.add(*questions_to_filter)

    response = graphql_client.execute(
        GET_QUESTIONNAIRE_DETAILS,
        variables={
            'id': questionnaire_id,
            'filters': dict(assignee=[NOT_ASSIGNED_USER_ID]),
        },
    )
    questionnaire_response = response['data']['questionnaireDetails']['questionnaire']

    assert len(questionnaire_response['questions']['data']) == 4


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_get_questionnaire_details_filtered(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    user: User,
):
    questionnaire = questionnaires[0]
    questionnaire_id = questionnaire.id
    questions_to_filter = create_questions_to_filter(graphql_organization, user)

    questionnaire.questions.add(*questions_to_filter)

    response = graphql_client.execute(
        GET_QUESTIONNAIRE_DETAILS,
        variables={
            'id': questionnaire_id,
            'filters': dict(assignee=[str(user.id)], status=[STATUS_COMPLETED]),
        },
    )
    questionnaire_response = response['data']['questionnaireDetails']['questionnaire']
    questions_filtered = questionnaire_response['questions']['data']

    assert len(questions_filtered) == 1
    assert questions_filtered[0]['id'] == '2'


# skip by UNACCENT not implemented in sqlite3
@pytest.mark.skip()
@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_get_questionnaire_details_filtered_by_search(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    user: User,
):
    questionnaire = questionnaires[0]
    questionnaire_id = questionnaire.id
    questions_to_filter = create_questions_to_filter(graphql_organization, user)

    questionnaire.questions.add(*questions_to_filter)

    response = graphql_client.execute(
        GET_QUESTIONNAIRE_DETAILS,
        variables={'id': questionnaire_id, 'filters': dict(search='search')},
    )
    questionnaire_response = response['data']['questionnaireDetails']['questionnaire']

    assert len(questionnaire_response['questions']['data']) == 2


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_get_questionnaire_details_paginated(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    user: User,
):
    questionnaire = questionnaires[0]
    questionnaire_id = questionnaire.id
    questions_to_filter = create_questions_to_filter(graphql_organization, user)

    questionnaire.questions.add(*questions_to_filter)

    response = graphql_client.execute(
        GET_QUESTIONNAIRE_DETAILS,
        variables={
            'id': questionnaire_id,
            'pagination': dict(page='1', pageSize='2'),
        },
    )
    print(response)
    questionnaire_response = response['data']['questionnaireDetails']['questionnaire']
    questions_first_page = questionnaire_response['questions']['data']
    pagination_result = questionnaire_response['questions']['pagination']

    assert len(questions_first_page) == 2
    assert questions_first_page[0]['id'] == '1'
    assert questions_first_page[1]['id'] == '2'
    assert pagination_result['current'] == 1
    assert pagination_result['hasNext'] is True
    assert pagination_result['page'] == 1
    assert pagination_result['pageSize'] == 2
    assert pagination_result['total'] == 6


@pytest.mark.functional(permissions=['library.change_libraryentry'])
def test_add_questions(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    question: Question,
):
    questionnaire = questionnaires[0]

    response = graphql_client.execute(
        CREATE_QUESTIONNAIRE_QUESTIONS,
        variables={
            'input': {
                'questionnaireId': questionnaire.id,
                'questions': [
                    {'text': 'New Question', 'metadata': json.dumps(question.metadata)}
                ],
            },
        },
    )
    questions = response['data']['createQuestionnaireQuestions']['questions']

    assert len(questions) == 1
    assert questionnaire.questions.count() == 2


@pytest.mark.functional(permissions=['library.change_libraryentry'])
def test_add_new_and_existing_questions(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire = questionnaires[0]
    question = questionnaire.questions.first()
    library_entry = LibraryEntry.objects.create(organization=questionnaire.organization)
    new_question = create_question_with_metadata(
        library_entry, 'Question non related to questionnaire', {}
    )

    response = graphql_client.execute(
        CREATE_QUESTIONNAIRE_QUESTIONS,
        variables={
            'input': {
                'questionnaireId': questionnaire.id,
                'questions': [
                    {'text': 'New Question', 'metadata': json.dumps(question.metadata)},
                    {'text': new_question.text, 'metadata': json.dumps({})},
                    {'text': question.text, 'metadata': json.dumps(question.metadata)},
                ],
            },
        },
    )
    questions = response['data']['createQuestionnaireQuestions']['questions']

    assert len(questions) == 3
    assert questionnaire.questions.count() == 3
    assert Question.objects.count() == 4
    assert Question.objects.filter(text=new_question.text).count() == 2


@pytest.mark.functional(permissions=['library.change_libraryentry'])
def test_duplicate_same_question_text_to_another_questionnaire(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    question: Question,
):
    questionnaire_one = questionnaires[0]
    questionnaire_two = questionnaires[1]
    questionnaire_two.completed = False
    questionnaire_two.save()

    response = graphql_client.execute(
        CREATE_QUESTIONNAIRE_QUESTIONS,
        variables={
            'input': {
                'questionnaireId': questionnaire_two.id,
                'questions': [
                    {'text': question.text, 'metadata': json.dumps(question.metadata)}
                ],
            },
        },
    )
    questions = response['data']['createQuestionnaireQuestions']['questions']

    question_id = int(questions[0].get('id'))

    assert len(questions) == 1
    assert questionnaire_one.questions.count() == 1
    assert questionnaire_two.questions.count() == 1
    assert questionnaire_two.questions.first().id == question_id
    assert Question.objects.filter(text=question.text).count() == 2


@pytest.mark.functional(permissions=['library.change_libraryentry'])
def test_update_question_with_existing_answer_address(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    question: Question,
    question_metadata,
):
    questionnaire = questionnaires[0]

    response = graphql_client.execute(
        CREATE_QUESTIONNAIRE_QUESTIONS,
        variables={
            'input': {
                'questionnaireId': questionnaire.id,
                'questions': [
                    {
                        'id': question.id,
                        'text': question.text,
                        'metadata': json.dumps(question_metadata),
                    }
                ],
            },
        },
    )
    questions = response['data']['createQuestionnaireQuestions']['questions']
    updated_question = Question.objects.get(text=question.text)
    assert len(questions) == 1
    assert questionnaire.questions.count() == 1
    assert updated_question.metadata.get('answerAddresses') == ['Sheet1!B1']


@pytest.mark.functional(permissions=['library.change_libraryentry'])
def test_update_question_with_new_answer_address(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    question: Question,
    question_metadata,
):
    questionnaire = questionnaires[0]

    question.metadata = question_metadata
    question.save()

    response = graphql_client.execute(
        CREATE_QUESTIONNAIRE_QUESTIONS,
        variables={
            'input': {
                'questionnaireId': questionnaire.id,
                'questions': [
                    {
                        'id': question.id,
                        'text': question.text,
                        'metadata': json.dumps(
                            {
                                **question_metadata,
                                'answer': {'address': 'Sheet1!D1', 'options': []},
                            }
                        ),
                    }
                ],
            },
        },
    )

    expected_answer = 'Sheet1!D1'
    questions = response['data']['createQuestionnaireQuestions']['questions']
    updated_question = Question.objects.get(text=question.text)

    assert len(questions) == 1
    assert questionnaire.questions.count() == 1
    assert updated_question.metadata.get('answer').get('address') == expected_answer


@pytest.mark.functional(permissions=['library.change_libraryentry'])
def test_overwrite_question_metadata(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    question: Question,
    question_metadata,
):
    questionnaire = questionnaires[0]

    question.metadata = question_metadata
    question.save()
    sheet = {'name': 'test', 'position': 1}

    response = graphql_client.execute(
        CREATE_QUESTIONNAIRE_QUESTIONS,
        variables={
            'input': {
                'overwriteAnswerAddresses': True,
                'questionnaireId': questionnaire.id,
                'questions': [
                    {
                        'id': question.id,
                        'text': question.text,
                        'metadata': json.dumps(
                            {
                                **question_metadata,
                                'sheet': sheet,
                                'answerAddresses': ['Sheet1!D1'],
                            }
                        ),
                    }
                ],
            },
        },
    )

    expected_answers = ['Sheet1!D1']
    questions = response['data']['createQuestionnaireQuestions']['questions']
    updated_question = Question.objects.get(text=question.text)

    assert len(questions) == 1
    assert questionnaire.questions.count() == 1
    assert updated_question.metadata.get('answerAddresses') == expected_answers
    assert updated_question.metadata.get('sheet') == sheet


@pytest.mark.functional(permissions=['library.change_libraryentry'])
def test_not_restore_question_does_not_belong_to_questionnaire(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    question: Question,
    deleted_question: Question,
    question_metadata,
):
    questionnaire = questionnaires[1]
    questionnaire.completed = False
    questionnaire.save()
    deleted_question.metadata = question_metadata
    deleted_question.save()

    response = graphql_client.execute(
        CREATE_QUESTIONNAIRE_QUESTIONS,
        variables={
            'input': {
                'questionnaireId': questionnaire.id,
                'questions': [
                    {
                        'id': question.id,
                        'text': question.text,
                        'metadata': json.dumps(question.metadata),
                    },
                    {
                        'id': deleted_question.id,
                        'text': deleted_question.text,
                        'metadata': json.dumps(
                            {
                                **question_metadata,
                                'answerAddresses': ['Sheet1!D1'],
                            }
                        ),
                    },
                ],
            },
        },
    )

    questions = response['data']['createQuestionnaireQuestions']['questions']

    questionnaire = Questionnaire.objects.get(id=questionnaire.id)
    try:
        Question.objects.get(id=deleted_question.id)
    except Question.DoesNotExist:
        assert True

    assert len(questions) == 2
    assert questionnaire.questions.count() == 2


@pytest.mark.functional(permissions=['library.change_libraryentry'])
def test_not_restore_deleted_question_from_another_questionnaire(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    question: Question,
    deleted_question: Question,
    question_metadata,
):
    questionnaire_one = questionnaires[0]
    questionnaire_two = questionnaires[1]
    questionnaire_one.questions.clear()
    deleted_question.save()
    questionnaire_two.questions.add(deleted_question)

    response = graphql_client.execute(
        CREATE_QUESTIONNAIRE_QUESTIONS,
        variables={
            'input': {
                'questionnaireId': questionnaire_one.id,
                'questions': [
                    {
                        'id': deleted_question.id,
                        'text': deleted_question.text,
                        'metadata': json.dumps(
                            {
                                **question_metadata,
                                'answerAddresses': ['Sheet1!D1'],
                            }
                        ),
                    }
                ],
            },
        },
    )

    questions = response['data']['createQuestionnaireQuestions']['questions']

    questionnaire = Questionnaire.objects.get(id=questionnaire_one.id)
    questionnaire_question = questionnaire.questions.first()

    assert 1 == questionnaire.questions.count()
    assert questionnaire_question.id == int(questions[0]['id'])
    assert deleted_question.id != questionnaire_question.id


@pytest.mark.functional(permissions=['library.delete_question'])
def test_soft_delete_questionnaire_questions_one_questionnaire(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire = questionnaires[0]

    response = graphql_client.execute(
        DELETE_QUESTIONNAIRE_QUESTIONS,
        variables={
            'input': {
                'questionnaireId': questionnaire.id,
                'questions': [{'text': QUESTION_TEXT, 'formulas': []}],
            },
        },
    )
    deleted = response['data']['deleteQuestionnaireQuestions']['deletedIds']

    questionnaire_related = Questionnaire.objects.get(id=questionnaire.id)
    assert len(deleted) == 1
    assert questionnaire_related.questions.count() == 0


@pytest.mark.parametrize(
    'delete_address, expected_answer, expected_short',
    [
        ('Sheet1!B2', 'Sheet1!B1', ''),
        ('Sheet1!B1', '', 'Sheet1!B2'),
    ],
)
@pytest.mark.functional(permissions=['library.delete_question'])
def test_do_not_soft_delete_question_with_multiple_addresses(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    question: Question,
    question_metadata,
    delete_address,
    expected_answer,
    expected_short,
):
    questionnaire = questionnaires[0]
    question.metadata = {
        **question_metadata,
        'answer': {'address': 'Sheet1!B1', 'options': []},
        'shortAnswer': {'address': 'Sheet1!B2', 'options': []},
    }
    question.save()

    response = graphql_client.execute(
        DELETE_QUESTIONNAIRE_QUESTIONS,
        variables={
            'input': {
                'questionnaireId': questionnaire.id,
                'questions': [{'text': question.text, 'formulas': [delete_address]}],
            },
        },
    )
    data = response['data']['deleteQuestionnaireQuestions']
    deleted = data['deletedIds']
    updated = data['updated']

    updated_question = Question.objects.get(id=question.id)
    assert len(deleted) == 0
    assert len(updated) == 1
    assert updated_question.metadata.get('answer').get('address') == expected_answer
    assert updated_question.metadata.get('shortAnswer').get('address') == expected_short


@pytest.mark.functional(permissions=['library.delete_question'])
def test_not_delete_questions_from_complete_questionnaire(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire = questionnaires[0]
    expected_questions = questionnaire.questions.all().count()
    questionnaire.completed = True
    questionnaire.save()

    response = graphql_client.execute(
        DELETE_QUESTIONNAIRE_QUESTIONS,
        variables={
            'input': {
                'questionnaireId': questionnaire.id,
                'questions': [{'text': QUESTION_TEXT, 'formulas': []}],
            },
        },
    )

    questionnaire_related = Questionnaire.objects.get(id=questionnaire.id)
    # This message is used in the Excel plugin
    assert response['errors'][0]['message'] == 'Cannot modify a completed questionnaire'
    assert questionnaire_related.questions.count() == expected_questions


@pytest.mark.functional(
    permissions=['library.delete_question', 'library.change_questionnaire']
)
def test_hard_delete_questionnaire_questions(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire = questionnaires[0]

    soft_delete_response = graphql_client.execute(
        DELETE_QUESTIONNAIRE_QUESTIONS,
        variables={
            'input': {
                'questionnaireId': questionnaire.id,
                'questions': [{'text': QUESTION_TEXT, 'formulas': []}],
            },
        },
    )

    questionnaire_ids = [questionnaire.id]

    update_questionnaire_response = graphql_client.execute(
        BULK_UPDATE_QUESTIONNAIRE_STATUS,
        variables={
            'input': dict(
                ids=questionnaire_ids,
                status=STATUS_COMPLETED,
            )
        },
    )
    hard_deleted_question = Question.objects.filter(
        id=soft_delete_response['data']['deleteQuestionnaireQuestions']['deletedIds'][0]
    )
    assert (
        int(
            update_questionnaire_response['data']['bulkUpdateQuestionnaireStatus'][
                'updated'
            ][0]
        )
        == questionnaire.id
    )
    assert len(hard_deleted_question) == 0


@pytest.mark.functional(
    permissions=['library.delete_question', 'library.change_questionnaire']
)
def test_soft_delete_question_with_multiple_formulas(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire = questionnaires[0]
    question = questionnaire.questions.first()
    question.metadata = {
        "answer": {"address": "Sheet1!B16", "options": []},
        "shortAnswer": {"address": "Sheet1!C16", "options": []},
        "questionAddress": "Sheet1!A16",
    }
    question.save()

    delete_response = graphql_client.execute(
        DELETE_QUESTIONNAIRE_QUESTIONS,
        variables={
            'input': {
                'questionnaireId': questionnaire.id,
                'questions': [
                    {'text': QUESTION_TEXT, 'formulas': ["Sheet1!B16"]},
                    {'text': QUESTION_TEXT, 'formulas': ["Sheet1!C16"]},
                ],
            },
        },
    )
    soft_deleted_question = Question.all_objects.get(id=question.id)

    assert soft_deleted_question.deleted_at
    assert delete_response['data']['deleteQuestionnaireQuestions']['deletedIds'] == [
        str(question.id)
    ]
    assert delete_response['data']['deleteQuestionnaireQuestions']['updated'] == []


@pytest.mark.functional(permissions=['library.delete_question'])
def test_soft_delete_questionnaire_questions_many_questionnaires(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    question: Question,
):
    questionnaire_1 = questionnaires[0]
    questionnaire_2 = questionnaires[1]
    library_entry = LibraryEntry.objects.create(organization=graphql_organization)
    new_question = Question.objects.create(
        text=question.text, library_entry=library_entry, default=True
    )
    questionnaire_2.questions.add(new_question)
    questionnaire_2.save()

    response = graphql_client.execute(
        DELETE_QUESTIONNAIRE_QUESTIONS,
        variables={
            'input': {
                'questionnaireId': questionnaire_1.id,
                'questions': [{'text': QUESTION_TEXT, 'formulas': []}],
            },
        },
    )
    data = response['data']['deleteQuestionnaireQuestions']
    deleted = data['deletedIds']
    updated = data['updated']

    questionnaire_without_question = Questionnaire.objects.get(id=questionnaire_1.id)
    questionnaire_with_question = Questionnaire.objects.get(id=questionnaire_2.id)
    question_to_delete = Question.all_objects.get(
        id=question.id, deleted_at__isnull=False
    )
    assert len(deleted) == 1
    assert len(updated) == 0
    assert questionnaire_without_question.questions.count() == 0
    assert questionnaire_with_question.questions.count() == 1
    assert question_to_delete is not None


@pytest.mark.functional(permissions=['library.change_libraryentry'])
def test_restore_deleted_questions(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    question: Question,
    deleted_question: Question,
):
    questionnaire = questionnaires[1]
    questionnaire.completed = False
    questionnaire.save()

    response = graphql_client.execute(
        CREATE_QUESTIONNAIRE_QUESTIONS,
        variables={
            'input': {
                'questionnaireId': questionnaire.id,
                'questions': [
                    {
                        'id': question.id,
                        'text': question.text,
                        'metadata': json.dumps(question.metadata),
                    },
                    {
                        'id': deleted_question.id,
                        'text': deleted_question.text,
                        'metadata': json.dumps(deleted_question.metadata),
                    },
                ],
            },
        },
    )

    questions_created = response['data']['createQuestionnaireQuestions']['questions']

    questionnaire = Questionnaire.objects.get(id=questionnaire.id)
    try:
        Question.objects.get(id=deleted_question.id)
    except Question.DoesNotExist:
        assert True

    assert len(questions_created) == 2
    assert questionnaire.questions.count() == 2
    assert Question.all_objects.count() == 4
    assert Question.objects.count() == 3


@pytest.mark.functional(permissions=['library.change_question'])
def test_update_question_assigned_user(
    graphql_client: Client,
    question: Question,
    questionnaires: List[Questionnaire],
    user: User,
):
    questionnaire = questionnaires[0]
    response = graphql_client.execute(
        UPDATE_QUESTION_ASSIGNED_USER,
        variables={
            'input': {
                'questionId': question.id,
                'questionnaireId': questionnaire.id,
                'userAssignedEmail': user.email,
            },
        },
    )
    question_updated = response['data']['updateQuestionAssignedUser']['question']

    question = Question.objects.get(id=question.id)

    assert question.user_assigned == user
    assert question.id == int(question_updated)


@pytest.mark.functional(permissions=['library.change_question'])
def test_alert_question_assigned(
    graphql_client: Client,
    question: Question,
    questionnaires: List[Questionnaire],
    user: User,
):
    questionnaire = questionnaires[0]
    graphql_client.execute(
        UPDATE_QUESTION_ASSIGNED_USER,
        variables={
            'input': {
                'questionId': question.id,
                'questionnaireId': questionnaire.id,
                'userAssignedEmail': user.email,
            },
        },
    )

    alert = QuestionnaireAlert.objects.filter(questionnaire_id=questionnaire.id)

    assert alert.count() == 1


@pytest.mark.functional(permissions=['library.change_question'])
def test_update_library_question_status_completed(
    graphql_client: Client, graphql_organization: Organization, question: Question
):
    response = graphql_client.execute(
        UPDATE_LIBRARY_QUESTION_STATUS,
        variables={
            'input': {
                'questionId': question.id,
                'status': STATUS_COMPLETED,
            },
        },
    )

    assert (
        len(response['data']['updateLibraryQuestionStatus']['updated']) == question.id
    )

    updated_question = Question.objects.get(id=question.id)

    assert updated_question.completed is True


@pytest.mark.functional(permissions=['library.change_question'])
def test_update_library_question_status_in_progress(
    graphql_client: Client,
    graphql_organization: Organization,
    completed_question: Question,
):
    response = graphql_client.execute(
        UPDATE_LIBRARY_QUESTION_STATUS,
        variables={
            'input': {
                'questionId': completed_question.id,
                'status': STATUS_IN_PROGRESS,
            },
        },
    )

    assert (
        len(response['data']['updateLibraryQuestionStatus']['updated'])
        == completed_question.id
    )

    updated_question = Question.objects.get(id=completed_question.id)

    assert updated_question.completed is False


@pytest.mark.functional(permissions=['library.change_question'])
def test_update_library_question_status_not_valid(
    graphql_client: Client, graphql_organization: Organization, question: Question
):
    response = graphql_client.execute(
        UPDATE_LIBRARY_QUESTION_STATUS,
        variables={
            'input': {
                'questionId': question.id,
                'status': 'non_existing_status',
            },
        },
    )

    assert response['errors'][0]['message'] == 'Invalid new status for question'


@pytest.mark.functional(permissions=['library.change_question'])
def test_update_library_question_completed_to_in_progress(
    graphql_client: Client,
    graphql_organization: Organization,
    completed_question: Question,
):
    completed_question.default = True
    completed_question.save()

    graphql_client.execute(
        UPDATE_QUESTION_ANSWER,
        variables={
            'input': {
                'questionId': completed_question.id,
                'answerType': 'answer',
                'answerText': 'Long answer text updated',
            },
        },
    )

    in_progress_question = Question.objects.get(id=completed_question.id)
    assert in_progress_question.completed is False


@pytest.mark.functional(permissions=['library.change_question'])
def test_add_equivalent_question(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire = questionnaires[0]
    question = questionnaire.questions.all()[0]
    q1 = create_question_with_metadata(
        create_library_entry(graphql_organization), f'{QUESTION_TEXT} - 1', {}
    )

    assert not question.equivalent_questions.filter(id=q1.id).exists()
    graphql_client.execute(
        ADD_EQUIVALENT_QUESTION,
        variables={'input': {'questionId': question.id, 'equivalentQuestionId': q1.id}},
    )

    assert question.equivalent_questions.filter(id=q1.id).exists()


@pytest.mark.functional(permissions=['library.change_question'])
def test_remove_equivalent_question(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire = questionnaires[0]
    question = questionnaire.questions.all()[0]
    q1 = create_question_with_metadata(
        create_library_entry(graphql_organization), f'{QUESTION_TEXT} - 1', {}
    )

    question.equivalent_questions.add(q1)

    graphql_client.execute(
        REMOVE_EQUIVALENT_QUESTION,
        variables={'input': {'questionId': question.id, 'equivalentQuestionId': q1.id}},
    )

    assert not question.equivalent_questions.filter(id=q1.id).exists()


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_equivalent_question_resolver(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire = questionnaires[0]
    question = questionnaire.questions.all()[0]
    q1 = create_question_with_metadata(
        create_library_entry(graphql_organization), f'{QUESTION_TEXT} - 1', {}
    )
    question.equivalent_questions.add(q1)

    response = graphql_client.execute(
        GET_QUESTIONNAIRE_DETAILS,
        variables={
            'id': questionnaire.id,
        },
    )
    questionnaire_response = response['data']['questionnaireDetails']['questionnaire']

    questionnaire_questions = questionnaire_response['questions']['data']
    equivalent_questions = questionnaire_questions[0]['equivalentQuestions']
    assert len(equivalent_questions) == 1
    assert equivalent_questions[0]['text'] == f'{QUESTION_TEXT} - 1'
    assert equivalent_questions[0]['default'] is True


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_equivalent_question_resolver_non_default(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    non_question_default,
):
    questionnaire = questionnaires[1]
    questionnaire.questions.add(non_question_default)

    q1 = create_question_with_metadata(
        create_library_entry(graphql_organization), f'{QUESTION_TEXT} - 1', {}
    )

    q1.equivalent_questions.add(non_question_default)

    response = graphql_client.execute(
        GET_QUESTIONNAIRE_DETAILS,
        variables={
            'id': questionnaire.id,
        },
    )
    questionnaire_response = response['data']['questionnaireDetails']['questionnaire']

    questionnaire_questions = questionnaire_response['questions']['data']
    equivalent_questions = questionnaire_questions[0]['equivalentQuestions']
    assert len(equivalent_questions) == 1
    assert equivalent_questions[0]['text'] == f'{QUESTION_TEXT} - 1'
    assert equivalent_questions[0]['default'] is True


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_fetch_exact_match_lowercase(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire_complete = questionnaires[0]
    questionnaire_complete.completed = True
    questionnaire_complete.save()

    questionnaire_incomplete = questionnaires[1]
    question_with_lowercase = create_question(
        graphql_organization=graphql_organization,
        question_text=QUESTION_TEXT_LOWERCASE,
        answer_text='',
    )
    questionnaire_incomplete.questions.add(question_with_lowercase)

    response = graphql_client.execute(
        FETCH_EXACT_MATCH,
        variables={
            'id': questionnaire_incomplete.id,
        },
    )
    fetch_response = response['data']['fetchDdqAnswers']['updated']
    assert len(fetch_response) == 1

    modified_question = Question.objects.get(id=question_with_lowercase.id)
    assert modified_question.library_entry.answer_text == ANSWER_TEXT
    assert len(modified_question.default_question.equivalent_questions.all()) == 1


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_fetch_exact_match_uppercase(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire_complete = questionnaires[0]
    questionnaire_complete.completed = True
    questionnaire_complete.save()

    questionnaire_incomplete = questionnaires[1]
    question_with_uppercase = create_question(
        graphql_organization=graphql_organization,
        question_text=QUESTION_TEXT_UPPERCASE,
        answer_text='',
    )
    questionnaire_incomplete.questions.add(question_with_uppercase)

    response = graphql_client.execute(
        FETCH_EXACT_MATCH,
        variables={
            'id': questionnaire_incomplete.id,
        },
    )
    fetch_response = response['data']['fetchDdqAnswers']['updated']
    assert len(fetch_response) == 1

    modified_question = Question.objects.get(id=question_with_uppercase.id)
    assert modified_question.library_entry.answer_text == ANSWER_TEXT
    assert len(modified_question.default_question.equivalent_questions.all()) == 1


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_fetch_exact_match_linebreak(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire_complete = questionnaires[0]
    questionnaire_complete.completed = True
    questionnaire_complete.save()

    questionnaire_incomplete = questionnaires[1]
    question_with_linebreak = create_question(
        graphql_organization=graphql_organization,
        question_text=QUESTION_TEXT_LINE_BREAK,
        answer_text='',
    )
    questionnaire_incomplete.questions.add(question_with_linebreak)

    response = graphql_client.execute(
        FETCH_EXACT_MATCH,
        variables={
            'id': questionnaire_incomplete.id,
        },
    )
    fetch_response = response['data']['fetchDdqAnswers']['updated']
    assert len(fetch_response) == 1

    modified_question = Question.objects.get(id=question_with_linebreak.id)
    assert modified_question.library_entry.answer_text == ANSWER_TEXT
    assert len(modified_question.default_question.equivalent_questions.all()) == 1


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_fetch_exact_match_tabs(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire_complete = questionnaires[0]
    questionnaire_complete.completed = True
    questionnaire_complete.save()

    questionnaire_incomplete = questionnaires[1]
    question_with_tabs = create_question(
        graphql_organization=graphql_organization,
        question_text=QUESTION_TEXT_TABS,
        answer_text='',
    )
    questionnaire_incomplete.questions.add(question_with_tabs)

    response = graphql_client.execute(
        FETCH_EXACT_MATCH,
        variables={
            'id': questionnaire_incomplete.id,
        },
    )
    fetch_response = response['data']['fetchDdqAnswers']['updated']
    assert len(fetch_response) == 1

    modified_question = Question.objects.get(id=question_with_tabs.id)
    assert modified_question.library_entry.answer_text == ANSWER_TEXT
    assert len(modified_question.default_question.equivalent_questions.all()) == 1


@pytest.mark.functional(
    permissions=['library.view_questionnaire', 'library.change_libraryentry']
)
def test_fetch_updates_question_fetched_value(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire_complete = questionnaires[0]
    questionnaire_complete.completed = True
    questionnaire_complete.save()

    questionnaire_incomplete = questionnaires[1]
    question_to_be_fetched = create_question(
        graphql_organization=graphql_organization,
        question_text=QUESTION_TEXT_LOWERCASE,
        answer_text='',
    )
    questionnaire_incomplete.questions.add(question_to_be_fetched)

    graphql_client.execute(
        FETCH_EXACT_MATCH,
        variables={
            'id': questionnaire_incomplete.id,
        },
    )

    modified_question = Question.objects.get(id=question_to_be_fetched.id)
    assert modified_question.fetch_status == RESULT_FOUND


@pytest.mark.functional(
    permissions=['library.view_questionnaire', 'library.change_question']
)
def test_update_answer_updates_fetched_value(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire_complete = questionnaires[0]
    questionnaire_complete.completed = True
    questionnaire_complete.save()

    questionnaire_incomplete = questionnaires[1]
    question_to_be_fetched = create_question(
        graphql_organization=graphql_organization,
        question_text=QUESTION_TEXT_LOWERCASE,
        answer_text='',
    )
    questionnaire_incomplete.questions.add(question_to_be_fetched)

    graphql_client.execute(
        FETCH_EXACT_MATCH,
        variables={
            'id': questionnaire_incomplete.id,
        },
    )

    question_fetched = Question.objects.get(id=question_to_be_fetched.id)
    assert question_fetched.fetch_status == RESULT_FOUND

    graphql_client.execute(
        UPDATE_QUESTION_ANSWER,
        variables={
            'input': {
                'questionId': question_to_be_fetched.id,
                'answerType': 'answer',
                'answerText': 'Long answer text updated',
            },
        },
    )

    question_updated = Question.objects.get(id=question_to_be_fetched.id)
    assert question_updated.fetch_status == RESULT_FOUND_UPDATED


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_fetch_exact_match_default_question_is_match(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire_complete = questionnaires[0]
    questionnaire_complete.completed = True
    questionnaire_complete.save()

    questionnaire_incomplete = questionnaires[1]
    question_with_lowercase = create_question(
        graphql_organization=graphql_organization,
        question_text=QUESTION_TEXT_LOWERCASE,
        answer_text='',
    )
    questionnaire_incomplete.questions.add(question_with_lowercase)

    graphql_client.execute(
        FETCH_EXACT_MATCH,
        variables={
            'id': questionnaire_incomplete.id,
        },
    )

    default_question = questionnaire_complete.questions.all().first()
    assert default_question.equivalent_questions.filter(
        id=question_with_lowercase.id
    ).exists()


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_fetch_exact_match_default_question_is_not_match(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire_with_default_question = questionnaires[0]
    questionnaire_with_default_question.completed = True
    questionnaire_with_default_question.save()

    questionnaire_with_non_default_question = questionnaires[1]
    non_default_question = create_question(
        graphql_organization=graphql_organization,
        question_text='NonDefaultQuestionText',
        answer_text='NonDefaultAnswerText',
        default=False,
    )
    questionnaire_with_non_default_question.questions.add(non_default_question)

    default_question = questionnaire_with_default_question.questions.all().first()
    default_question.equivalent_questions.add(non_default_question)
    default_question.save()

    questionnaire_incomplete = questionnaires[2]
    questionnaire_incomplete.completed = False
    question_with_exact_match_text = create_question(
        graphql_organization=graphql_organization,
        question_text='NonDefaultQuestionText',
        answer_text='',
    )
    questionnaire_incomplete.questions.add(question_with_exact_match_text)
    questionnaire_incomplete.save()

    graphql_client.execute(
        FETCH_EXACT_MATCH,
        variables={
            'id': questionnaire_incomplete.id,
        },
    )

    default_question = questionnaire_with_default_question.questions.all().first()
    assert default_question.equivalent_questions.filter(
        id=non_default_question.id
    ).exists()
    assert default_question.equivalent_questions.filter(
        id=question_with_exact_match_text.id
    ).exists()


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_fetch_fuzzy_exact_match(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire_complete = questionnaires[0]
    questionnaire_complete.completed = True
    questionnaire_complete.save()

    questionnaire_incomplete = questionnaires[1]
    question_with_lowercase = create_question(
        graphql_organization=graphql_organization,
        question_text=QUESTION_TEXT_LOWERCASE,
        answer_text='',
    )
    questionnaire_incomplete.questions.add(question_with_lowercase)

    response = graphql_client.execute(
        FETCH_FUZZY_MATCH,
        variables={'id': questionnaire_incomplete.id, 'fetchType': 'fuzzy'},
    )
    fetch_response = response['data']['fetchDdqAnswers']['updated']
    assert len(fetch_response) == 1

    modified_question = Question.objects.get(id=question_with_lowercase.id)
    assert modified_question.library_entry.answer_text == ANSWER_TEXT
    assert len(modified_question.default_question.equivalent_questions.all()) == 1


# Test skiped because Trigram Similarity is not suported in unit test bd.
@pytest.mark.skip()
@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_fetch_fuzzy_match_lowercase(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
):
    questionnaire_complete = questionnaires[0]
    questionnaire_complete.completed = True
    questionnaire_complete.save()

    questionnaire_incomplete = questionnaires[1]
    question_with_lowercase = create_question(
        graphql_organization=graphql_organization,
        question_text=QUESTION_TEXT_LOWERCASE_FUZZY,
        answer_text='',
    )
    questionnaire_incomplete.questions.add(question_with_lowercase)

    response = graphql_client.execute(
        FETCH_FUZZY_MATCH,
        variables={'id': questionnaire_incomplete.id, 'fetchType': 'fuzzy'},
    )
    fetch_response = response['data']['fetchDdqAnswers']['updated']
    assert len(fetch_response) == 1

    modified_question = Question.objects.get(id=question_with_lowercase.id)
    assert modified_question.library_entry.answer_text == ANSWER_TEXT
    assert len(modified_question.default_question.equivalent_questions.all()) == 1


@pytest.mark.functional(permissions=['library.change_question'])
def test_update_question_short_answer_fetched(
    graphql_client: Client,
    question: Question,
):
    question.fetch_status = RESULT_FOUND
    question.completed = True
    question.save()
    response = graphql_client.execute(
        UPDATE_QUESTION_ANSWER,
        variables={
            'input': {
                'questionId': question.id,
                'answerType': 'shortAnswer',
                'answerText': 'Short answer text updated',
            },
        },
    )
    question_updated = response['data']['updateQuestionAnswer']['updated']

    question = Question.objects.get(id=question.id)

    assert question_updated
    assert question.library_entry.short_answer_text == 'Short answer text updated'
    assert question.fetch_status == RESULT_FOUND
    assert not question.completed


@pytest.mark.functional(permissions=['library.change_question'])
def test_update_question_short_answer_not_fetched(
    graphql_client: Client,
    question: Question,
):
    question.fetch_status = NOT_RAN
    question.completed = True
    question.save()
    response = graphql_client.execute(
        UPDATE_QUESTION_ANSWER,
        variables={
            'input': {
                'questionId': question.id,
                'answerType': 'shortAnswer',
                'answerText': 'Short answer text updated',
            },
        },
    )
    question_updated = response['data']['updateQuestionAnswer']['updated']

    question = Question.objects.get(id=question.id)

    assert question_updated
    assert question.library_entry.short_answer_text == 'Short answer text updated'
    assert question.fetch_status == NOT_RAN
    assert not question.completed


@pytest.mark.functional(permissions=['library.change_question'])
def test_update_question_long_answer(graphql_client: Client, question: Question):
    question.fetch_status = RESULT_FOUND
    question.completed = True
    question.save()
    response = graphql_client.execute(
        UPDATE_QUESTION_ANSWER,
        variables={
            'input': {
                'questionId': question.id,
                'answerType': 'answer',
                'answerText': 'Long answer updated',
            },
        },
    )
    question_updated = response['data']['updateQuestionAnswer']['updated']

    question = Question.objects.get(id=question.id)

    assert question_updated
    assert question.library_entry.answer_text == 'Long answer updated'
    assert question.fetch_status == RESULT_FOUND_UPDATED
    assert not question.completed


@pytest.mark.functional(permissions=['library.change_question'])
def test_update_question_answer_wrong_answer_type(
    graphql_client: Client, question: Question
):
    response = graphql_client.execute(
        UPDATE_QUESTION_ANSWER,
        variables={
            'input': {
                'questionId': question.id,
                'answerType': 'WRONG ANSWER TYPE',
                'answerText': 'Long answer updated',
            },
        },
    )
    assert (
        response['errors'][0]['message'] == 'Invalid answer type for updating question'
    )


@pytest.mark.functional(permissions=['library.change_question'])
def test_update_non_default_equivalent_question_updates_equivalent_questions(
    graphql_client: Client, graphql_organization: Organization
):
    default_question = create_question(graphql_organization, default=True)
    second_question = create_question(graphql_organization, default=False)
    third_question = create_question(graphql_organization, default=False)
    default_question.equivalent_questions.add(*[second_question, third_question])

    graphql_client.execute(
        UPDATE_QUESTION_ANSWER,
        variables={
            'input': {
                'questionId': third_question.id,
                'answerType': 'answer',
                'answerText': 'Long answer updated',
            },
        },
    )

    assert (
        Question.objects.get(id=default_question.id).equivalent_questions.count() == 1
    )


@pytest.mark.functional(
    permissions=['library.view_questionnaire', 'library.change_libraryentry']
)
def test_try_to_create_question_for_completed_questionnaire_should_fail(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    question: Question,
):
    questionnaire = questionnaires[1]

    response = graphql_client.execute(
        CREATE_QUESTIONNAIRE_QUESTIONS,
        variables={
            'input': {
                'questionnaireId': questionnaire.id,
                'questions': [
                    {'text': question.text, 'metadata': json.dumps(question.metadata)}
                ],
            },
        },
    )

    # This message is used in the Excel plugin
    assert response['errors'][0]['message'] == 'Cannot modify a completed questionnaire'


@pytest.mark.functional(
    permissions=['library.view_questionnaire', 'library.change_libraryentry']
)
def test_try_to_delete_question_for_completed_questionnaire_should_fail(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    question: Question,
):
    questionnaire = questionnaires[0]
    graphql_client.execute(
        CREATE_QUESTIONNAIRE_QUESTIONS,
        variables={
            'input': {
                'questionnaireId': questionnaire.id,
                'questions': [
                    {'text': question.text, 'metadata': json.dumps(question.metadata)}
                ],
            },
        },
    )

    questionnaire.completed = True
    questionnaire.save()

    response = graphql_client.execute(
        DELETE_QUESTIONNAIRE_QUESTIONS,
        variables={
            'input': {
                'questionnaireId': questionnaire.id,
                'questions': [{'text': QUESTION_TEXT, 'formulas': []}],
            },
        },
    )
    assert (
        response['errors'][0]['message']
        == 'Failed to delete questionnaire question. Please try again.'
    )


@pytest.mark.functional(permissions=['library.view_libraryentry'])
def test_get_library_questions(
    graphql_client: Client, graphql_organization: Organization
):
    q1 = create_question(
        graphql_organization=graphql_organization,
    )
    create_questionnaire(
        name='Completed questionnaire',
        organization=graphql_organization,
        with_question=True,
        question=q1,
        completed=True,
    )
    response = graphql_client.execute(
        GET_LIBRARY_QUESTIONS,
        variables={
            'filter': {'text': ''},
            'pagination': {'page': 1, 'pageSize': 50},
            'orderBy': [{'field': 'created_at', 'order': 'descend'}],
        },
    )
    data = response['data']['libraryQuestions']
    assert len(data['libraryQuestions']) == 1
    assert data['hasLibraryQuestions'] is True


@pytest.mark.functional(permissions=['library.view_libraryentry'])
def test_get_library_questions_without_questionnaire(
    graphql_client: Client, graphql_organization: Organization
):
    q1 = create_question(
        graphql_organization=graphql_organization,
    )
    create_question(
        graphql_organization=graphql_organization,
    )
    create_question(
        graphql_organization=graphql_organization,
    )
    create_questionnaire(
        name='Completed questionnaire',
        organization=graphql_organization,
        with_question=True,
        question=q1,
        completed=True,
    )
    response = graphql_client.execute(
        GET_LIBRARY_QUESTIONS,
        variables={
            'filter': {'text': ''},
            'pagination': {'page': 1, 'pageSize': 50},
            'orderBy': [{'field': 'created_at', 'order': 'descend'}],
        },
    )
    data = response['data']['libraryQuestions']
    assert len(data['libraryQuestions']) == 3
    assert data['hasLibraryQuestions'] is True


@pytest.mark.functional(permissions=['library.view_libraryentry'])
def test_get_library_questions_without_in_progress_equivalent_questions(
    graphql_client: Client, graphql_organization: Organization
):
    default_question = create_question(
        graphql_organization=graphql_organization,
    )
    q1 = create_question(
        graphql_organization=graphql_organization,
    )
    create_question(
        graphql_organization=graphql_organization,
    )
    default_question.equivalent_questions.add(q1)
    create_questionnaire(
        name='Incomplete questionnaire',
        organization=graphql_organization,
        with_question=True,
        question=q1,
        completed=False,
    )
    response = graphql_client.execute(
        GET_LIBRARY_QUESTIONS,
        variables={
            'filter': {'text': ''},
            'pagination': {'page': 1, 'pageSize': 50},
            'orderBy': [{'field': 'created_at', 'order': 'ascend'}],
        },
    )
    data = response['data']['libraryQuestions']
    assert len(data['libraryQuestions'][0]['equivalentQuestions']) == 0
    assert len(data['libraryQuestions']) == 2
    assert data['hasLibraryQuestions'] is True


@pytest.mark.functional(permissions=['library.view_libraryentry'])
def test_no_return_get_library_questions_from_incompleted_questionanires(
    graphql_client: Client, graphql_organization: Organization
):
    q1 = create_question(
        graphql_organization=graphql_organization,
    )
    create_questionnaire(
        name='Completed questionnaire',
        organization=graphql_organization,
        with_question=True,
        question=q1,
        completed=False,
    )
    response = graphql_client.execute(
        GET_LIBRARY_QUESTIONS,
        variables={
            'filter': {'text': ''},
            'pagination': {'page': 1, 'pageSize': 50},
            'orderBy': [{'field': 'created_at', 'order': 'descend'}],
        },
    )
    data = response['data']['libraryQuestions']
    assert len(data['libraryQuestions']) == 0
    assert data['hasLibraryQuestions'] is False


@pytest.mark.functional(permissions=['library.view_libraryentry'])
def test_get_library_questions_no_questionnaire_uncompleted_questionnaire(
    graphql_client: Client, graphql_organization: Organization
):
    q1 = create_question(
        graphql_organization=graphql_organization,
    )
    create_question(
        graphql_organization=graphql_organization,
    )
    create_question(
        graphql_organization=graphql_organization,
    )
    create_questionnaire(
        name='Completed questionnaire',
        organization=graphql_organization,
        with_question=True,
        question=q1,
        completed=False,
    )
    response = graphql_client.execute(
        GET_LIBRARY_QUESTIONS,
        variables={
            'filter': {'text': ''},
            'pagination': {'page': 1, 'pageSize': 50},
            'orderBy': [{'field': 'created_at', 'order': 'descend'}],
        },
    )
    data = response['data']['libraryQuestions']
    assert len(data['libraryQuestions']) == 2
    assert data['hasLibraryQuestions'] is True


@pytest.mark.parametrize(
    'order, result',
    [
        (
            'ascend',
            [
                OrderedDict(
                    [
                        ('id', '1'),
                        ('text', 'Question Example'),
                        ('completed', False),
                        ('equivalentQuestions', []),
                    ]
                ),
                OrderedDict(
                    [
                        ('id', '2'),
                        ('text', 'Question Example'),
                        ('completed', False),
                        ('equivalentQuestions', []),
                    ]
                ),
                OrderedDict(
                    [
                        ('id', '3'),
                        ('text', 'Question Example'),
                        ('completed', False),
                        ('equivalentQuestions', []),
                    ]
                ),
            ],
        ),
        (
            'descend',
            [
                OrderedDict(
                    [
                        ('id', '3'),
                        ('text', 'Question Example'),
                        ('completed', False),
                        ('equivalentQuestions', []),
                    ]
                ),
                OrderedDict(
                    [
                        ('id', '2'),
                        ('text', 'Question Example'),
                        ('completed', False),
                        ('equivalentQuestions', []),
                    ]
                ),
                OrderedDict(
                    [
                        ('id', '1'),
                        ('text', 'Question Example'),
                        ('completed', False),
                        ('equivalentQuestions', []),
                    ]
                ),
            ],
        ),
    ],
)
@pytest.mark.functional(permissions=['library.view_libraryentry'])
def test_get_library_questions_sort(
    order, result, graphql_client: Client, graphql_organization: Organization
):
    q1 = create_question(
        graphql_organization=graphql_organization,
    )
    create_question(
        graphql_organization=graphql_organization,
    )
    create_question(
        graphql_organization=graphql_organization,
    )
    create_questionnaire(
        name='Completed questionnaire',
        organization=graphql_organization,
        with_question=True,
        question=q1,
        completed=True,
    )
    response = graphql_client.execute(
        GET_LIBRARY_QUESTIONS,
        variables={
            'filter': {'text': ''},
            'pagination': {'page': 1, 'pageSize': 50},
            'orderBy': [{'field': 'created_at', 'order': order}],
        },
    )
    data = response['data']['libraryQuestions']
    assert data['libraryQuestions'] == result
    assert data['hasLibraryQuestions'] is True


@pytest.mark.functional(permissions=['library.view_libraryentry'])
def test_get_library_questions_ordered_by_updated_at(
    graphql_client: Client, graphql_organization: Organization
):
    q1 = create_question(
        graphql_organization=graphql_organization,
    )
    create_question(
        graphql_organization=graphql_organization,
    )
    q1.library_entry.answer_text = 'Some text'
    q1.library_entry.save()
    response = graphql_client.execute(
        GET_LIBRARY_QUESTIONS,
        variables={
            'filter': {'text': ''},
            'pagination': {'page': 1, 'pageSize': 50},
            'orderBy': [{'field': 'updated_at', 'order': 'descend'}],
        },
    )
    data = response['data']['libraryQuestions']
    assert data['libraryQuestions'][0]['id'] == str(q1.id)


@pytest.mark.functional(permissions=['library.view_libraryentry'])
def test_get_library_questions_pagination(
    graphql_client: Client, graphql_organization: Organization
):
    q1 = create_question(
        graphql_organization=graphql_organization,
    )
    q2 = create_question(
        graphql_organization=graphql_organization,
    )
    questionnaire = create_questionnaire(
        name='Completed questionnaire',
        organization=graphql_organization,
        with_question=True,
        question=q1,
        completed=True,
    )
    questionnaire.questions.add(q2)
    questionnaire.save()
    response = graphql_client.execute(
        GET_LIBRARY_QUESTIONS,
        variables={
            'filter': {'text': ''},
            'pagination': {'page': 1, 'pageSize': 1},
            'orderBy': [{'field': 'created_at', 'order': 'descend'}],
        },
    )
    data = response['data']['libraryQuestions']
    assert len(data['libraryQuestions']) == 1
    assert data['pagination']['current'] == 1
    assert data['pagination']['pageSize'] == 1
    assert data['pagination']['total'] == 2
    assert data['pagination']['hasNext']
    assert data['hasLibraryQuestions'] is True

    response = graphql_client.execute(
        GET_LIBRARY_QUESTIONS,
        variables={
            'filter': {'text': ''},
            'pagination': {'page': 2, 'pageSize': 1},
            'orderBy': [{'field': 'created_at', 'order': 'descend'}],
        },
    )

    data = response['data']['libraryQuestions']
    assert len(data['libraryQuestions']) == 1
    assert data['pagination']['current'] == 2
    assert data['pagination']['pageSize'] == 1
    assert data['pagination']['total'] == 2
    assert not data['pagination']['hasNext']
    assert data['hasLibraryQuestions'] is True


@pytest.mark.functional(permissions=['library.change_libraryentry'])
def test_update_library_question(
    graphql_client: Client, graphql_organization: Organization
):
    q1 = create_question(
        graphql_organization=graphql_organization,
    )
    response = graphql_client.execute(
        UPDATE_LIBRARY_QUESTION,
        variables={
            'input': {
                'questionId': q1.id,
                'questionText': 'New Question Text',
                'answer': {'text': 'New answer text', 'shortText': 'Yes'},
            }
        },
    )
    updated = response['data']['updateLibraryQuestion']['updated']
    assert updated


@pytest.mark.functional(permissions=['library.change_libraryentry'])
def test_update_library_question_required_id(
    graphql_client: Client, graphql_organization: Organization
):
    create_question(
        graphql_organization=graphql_organization,
    )
    response = graphql_client.execute(
        UPDATE_LIBRARY_QUESTION, variables={'input': {'something': 0}}
    )
    assert 'errors' in response


@pytest.mark.functional(permissions=['library.delete_question'])
def test_delete_library_question_without_equivalent_questions(
    graphql_client: Client,
    graphql_organization: Organization,
    question: Question,
):
    response = graphql_client.execute(
        DELETE_LIBRARY_QUESTION,
        variables={
            'input': dict(
                questionId=question.id,
            )
        },
    )['data']['deleteLibraryQuestion']['deleted']

    assert response is True
    assert not Question.objects.filter(
        id=question.id, library_entry__organization__id=graphql_organization.id
    ).exists()


@pytest.mark.functional(permissions=['library.delete_question'])
def test_delete_library_question_with_equivalent_questions(
    graphql_client: Client,
    graphql_organization: Organization,
    question: Question,
    non_question_default: Question,
):
    question_in_progress_questionnaire = create_question(
        graphql_organization, default=False
    )
    question_completed_questionnaire = create_question(
        graphql_organization, default=False
    )
    in_progress_questionnaire = Questionnaire.objects.create(
        name='Incomplete', organization=graphql_organization, completed=False
    )
    completed_questionnaire = Questionnaire.objects.create(
        name='Complete', organization=graphql_organization, completed=True
    )
    in_progress_questionnaire.questions.add(question_in_progress_questionnaire)
    completed_questionnaire.questions.add(question_completed_questionnaire)
    question.equivalent_questions.add(non_question_default)
    question.equivalent_questions.add(question_in_progress_questionnaire)
    question.equivalent_questions.add(question_completed_questionnaire)

    response = graphql_client.execute(
        DELETE_LIBRARY_QUESTION,
        variables={
            'input': dict(
                questionId=question.id,
            )
        },
    )['data']['deleteLibraryQuestion']['deleted']

    assert response is True
    assert not Question.objects.filter(
        id=question.id, library_entry__organization__id=graphql_organization.id
    ).exists()
    assert not Question.objects.filter(
        id=question_completed_questionnaire.id,
        library_entry__organization__id=graphql_organization.id,
    ).exists()
    assert not Question.objects.filter(
        id=non_question_default.id,
        library_entry__organization__id=graphql_organization.id,
    ).exists()
    assert Question.objects.filter(
        id=question_in_progress_questionnaire.id,
        library_entry__organization__id=graphql_organization.id,
        default=True,
    ).exists()


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_progress_completed_questions(
    graphql_client: Client,
    graphql_organization: Organization,
    questionnaires: List[Questionnaire],
    user: User,
):
    questionnaire = questionnaires[0]
    questionnaire_id = questionnaire.id
    questions_to_filter = create_questions_to_filter(graphql_organization, user)

    questionnaire.questions.add(*questions_to_filter)

    response = graphql_client.execute(
        GET_QUESTIONNAIRE_DETAILS,
        variables={'id': questionnaire_id, 'filters': dict(status=[STATUS_COMPLETED])},
    )
    questionnaire_response = response['data']['questionnaireDetails']['questionnaire']
    progress = questionnaire_response['progress']
    assert len(questionnaire_response['questions']) == progress['completed']
    assert progress['total'] == questionnaire.questions.count()


@pytest.mark.functional(permissions=['library.view_questionnaire'])
def test_progress_completed_questions_for_empty_questionnaire(
    graphql_client: Client,
    questionnaires: List[Questionnaire],
):
    questionnaire = questionnaires[1]
    questionnaire_id = questionnaire.id

    response = graphql_client.execute(
        GET_QUESTIONNAIRE_DETAILS, variables={'id': questionnaire_id}
    )
    questionnaire_response = response['data']['questionnaireDetails']['questionnaire']
    progress = questionnaire_response['progress']
    assert questionnaire.questions.count() == 0
    assert len(questionnaire_response['questions']['data']) == 0
    assert progress['completed'] == 0
    assert progress['total'] == 0
    assert progress['percent'] == 0


@pytest.mark.functional(permissions=['library.view_libraryentry'])
def test_get_questions_with_suggestions(
    graphql_client: Client,
    graphql_organization: Organization,
    question: Question,
):
    other_question = create_question(graphql_organization)
    question.equivalent_suggestions.add(other_question)

    response = graphql_client.execute(GET_QUESTIONS_WITH_SUGGESTIONS)
    suggestions_response = response['data']['questionsWithSuggestions']
    suggestions = suggestions_response['suggestions']
    has_suggestions = suggestions_response['hasSuggestions']

    assert len(suggestions) == 1
    assert has_suggestions is True

    question_with_suggestions = suggestions[0]
    equivalent_suggestions = question_with_suggestions['equivalentSuggestions']

    assert len(equivalent_suggestions) == 1
    assert int(equivalent_suggestions[0]['id']) == other_question.id


@pytest.mark.functional(permissions=['library.view_libraryentry'])
def test_get_questions_without_suggestions(
    graphql_client: Client,
):
    response = graphql_client.execute(GET_QUESTIONS_WITH_SUGGESTIONS)
    suggestions_response = response['data']['questionsWithSuggestions']
    suggestions = suggestions_response['suggestions']
    has_suggestions = suggestions_response['hasSuggestions']

    assert len(suggestions) == 0
    assert has_suggestions is False


@pytest.mark.functional(permissions=['library.change_libraryentry'])
def test_resolve_equivalent_suggestion(
    graphql_client: Client,
    graphql_organization: Organization,
    user: User,
    suggestion_questions: Tuple[Question, Question],
):
    question_1, question_2 = suggestion_questions
    response = graphql_client.execute(
        RESOLVE_EQUIVALENT_SUGGESTION,
        variables={
            'input': {
                'existingQuestionId': question_1.id,
                'equivalentSuggestionId': question_2.id,
                'chosenQuestionId': question_1.id,
                'answerText': '',
            }
        },
    )
    alerts = Alert.objects.filter(
        receiver=user, type=ALERT_TYPES['LIBRARY_ENTRY_SUGGESTIONS']
    )
    suggestions_alerts = LibraryEntrySuggestionsAlert.objects.filter(alert__in=alerts)
    suggestion_response = response['data']['resolveEquivalentSuggestion']['resolved']

    assert suggestion_response is True
    assert alerts.count() == 0
    assert suggestions_alerts.count() == 0


@pytest.mark.functional(permissions=['library.delete_question'])
def test_delete_library_question_in_equivalent_suggestions(
    graphql_client: Client,
    suggestion_questions: Tuple[Question, Question],
):
    question, _ = suggestion_questions
    equivalent_suggestion_from_question = question.equivalent_suggestions.first()

    assert len(question.equivalent_suggestions.all()) == 2

    response = graphql_client.execute(
        DELETE_LIBRARY_QUESTION,
        variables={
            'input': dict(
                questionId=equivalent_suggestion_from_question.id,
            )
        },
    )['data']['deleteLibraryQuestion']['deleted']

    assert response is True

    question_updated = Question.objects.get(id=question.id)
    assert len(question_updated.equivalent_suggestions.all()) == 1
    assert not question_updated.equivalent_suggestions.filter(
        id=equivalent_suggestion_from_question.id
    ).exists()


@pytest.mark.functional(permissions=['library.delete_question'])
def test_delete_library_organizations_suggestions(
    graphql_client: Client,
    suggestion_questions: Tuple[Question, Question],
    user: User,
):
    question_1, question_2 = suggestion_questions
    create_suggestion_alert(user, 2)

    graphql_client.execute(
        DELETE_LIBRARY_QUESTION,
        variables={
            'input': dict(
                questionId=question_1.id,
            )
        },
    )
    graphql_client.execute(
        DELETE_LIBRARY_QUESTION,
        variables={
            'input': dict(
                questionId=question_2.id,
            )
        },
    )

    alerts = Alert.objects.filter(
        receiver=user, type=ALERT_TYPES['LIBRARY_ENTRY_SUGGESTIONS']
    )
    suggestions_alerts = LibraryEntrySuggestionsAlert.objects.filter(alert__in=alerts)
    assert alerts.count() == 0
    assert suggestions_alerts.count() == 0


@pytest.mark.functional(permissions=['library.bulk_upload_library'])
def test_bulk_upload_library_error(
    graphql_client: Client,
):
    with patch(
        'laika.utils.schema_builder.template_builder.TemplateBuilder.parse',
        return_value={
            'Library': SchemaResponse(
                error=ServiceException('Missing sheet Library'),
                failed_rows=[],
                success_rows=[],
            )
        },
    ):
        response = graphql_client.execute(
            BULK_LIBRARY_UPLOAD,
            variables={
                'input': dict(
                    libraryFile={},
                )
            },
        )
        assert response['errors'][0]['message'] == 'Missing sheet Library'


@pytest.mark.functional(permissions=['library.bulk_upload_library'])
def test_bulk_upload_library_error_failed_rows(
    graphql_client: Client,
):
    with patch(
        'laika.utils.schema_builder.template_builder.TemplateBuilder.parse',
        return_value={
            'Library': SchemaResponse(
                error=None,
                failed_rows=[
                    RequiredErrorType(
                        field='Question', address='A3', description='Required Field'
                    )
                ],
                success_rows=[],
            )
        },
    ):
        response = graphql_client.execute(
            BULK_LIBRARY_UPLOAD,
            variables={
                'input': dict(
                    libraryFile={},
                )
            },
        )
        assert response['data']['bulkLibraryUpload']['uploadResult']['failedRows'] == [
            dict(type='required_value', addresses=['A3'])
        ]


@pytest.mark.functional(permissions=['library.bulk_upload_library'])
def test_bulk_upload_library_error_no_questions(
    graphql_client: Client,
):
    with patch(
        'laika.utils.schema_builder.template_builder.TemplateBuilder.parse',
        return_value={
            'Library': SchemaResponse(error=None, failed_rows=[], success_rows=[])
        },
    ):
        response = graphql_client.execute(
            BULK_LIBRARY_UPLOAD,
            variables={
                'input': dict(
                    libraryFile={},
                )
            },
        )
        assert response['errors'][0]['message'] == 'No questions were added in the file'


@pytest.mark.functional(permissions=['library.bulk_upload_library'])
def test_bulk_upload_library_success(
    graphql_client: Client,
):
    with patch(
        'laika.utils.schema_builder.template_builder.TemplateBuilder.parse',
        return_value={
            'Library': SchemaResponse(
                error=None,
                failed_rows=[],
                success_rows=[
                    {
                        'Question': 'Question Test',
                        'Category': 'Capacity & Performance Planning',
                        'Answer': 'Answer Test',
                        'Short Answer': 'Short Answer Test',
                    }
                ],
            )
        },
    ):
        graphql_client.execute(
            BULK_LIBRARY_UPLOAD,
            variables={
                'input': dict(
                    libraryFile={},
                )
            },
        )
        question_created = Question.objects.filter(
            text='Question Test',
            library_entry__answer_text='Answer Test',
            library_entry__short_answer_text='Short Answer Test',
        ).exists()

        assert question_created is True


@pytest.mark.functional(permissions=['library.view_libraryentry'])
def test_get_library_tasks(graphql_client: Client, user: User):
    LibraryTask.objects.create(created_by=user)
    LibraryTask.objects.create(created_by=user, status=TASK_COMPLETED_STATUS)

    response = graphql_client.execute(GET_LIBRARY_TASKS)
    library_tasks = response['data']['libraryTasks']['libraryTasks']

    assert len(library_tasks) == 2
    assert library_tasks[0]['finished'] is False
    assert library_tasks[1]['finished'] is True


@pytest.mark.functional(permissions=['dataroom.add_dataroomevidence'])
def test_add_dataroom_questionnaire_documents(
    graphql_client: Client,
    questionnaires: List[Questionnaire],
    dataroom: Dataroom,
    drive_evidence: DriveEvidence,
):
    questionnaire = questionnaires[0]
    questionnaire.dataroom = dataroom
    questionnaire.save()

    response = graphql_client.execute(
        ADD_DOCUMENTS_QUESTIONNAIRE_DATAROOM,
        variables={
            'input': dict(
                questionnaireName=questionnaire.name,
                documents=drive_evidence.id,
                timeZone='utc',
            )
        },
    )
    assert (
        len(response['data']['addDocumentsQuestionnaireDataroom']['documentIds']) == 1
    )


@pytest.mark.functional(permissions=['dataroom.add_dataroomevidence'])
def test_add_dataroom_questionnaire_documents_dataroom_not_exists(
    graphql_client: Client,
    questionnaires: List[Questionnaire],
    drive_evidence: DriveEvidence,
    graphql_organization: Organization,
):
    questionnaire = questionnaires[0]

    response = graphql_client.execute(
        ADD_DOCUMENTS_QUESTIONNAIRE_DATAROOM,
        variables={
            'input': dict(
                questionnaireName=questionnaire.name,
                documents=drive_evidence.id,
                timeZone='utc',
            )
        },
    )
    assert (
        len(response['data']['addDocumentsQuestionnaireDataroom']['documentIds']) == 1
    )
    dataroom_created = Dataroom.objects.filter(
        name=f'{questionnaire.name} Dataroom', organization=graphql_organization
    )
    questionnaire_modified = Questionnaire.objects.get(id=questionnaire.id)
    assert dataroom_created.exists()
    assert questionnaire_modified.dataroom.id == dataroom_created[0].id

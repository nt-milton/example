from typing import Tuple, Union

from alert.constants import ALERT_TYPES
from library.constants import NOT_RAN
from library.models import LibraryEntry, LibraryEntrySuggestionsAlert, Question
from organization.models import Organization
from user.models import User

QUESTION_TEXT = 'Question Example'
ANSWER_TEXT = 'Answer Example'
EXISTING_QUESTION_TEXT = 'Existing Question'
IMPORTED_QUESTION_TEXT = 'Imported Question'
EXISTING_QUESTION_ANSWER_TEXT = 'Existing Question Answer'
IMPORTED_QUESTION_ANSWER_TEXT = 'Imported Question Answer'


def create_library_entry(
    graphql_organization: Organization, answer_text=ANSWER_TEXT
) -> LibraryEntry:
    return LibraryEntry.objects.create(
        organization=graphql_organization,
        answer_text=answer_text,
    )


def create_question(
    graphql_organization: Organization,
    answer_text=ANSWER_TEXT,
    question_text=QUESTION_TEXT,
    default=True,
    fetch_status=NOT_RAN,
) -> Question:
    entry = create_library_entry(graphql_organization, answer_text)
    return Question.objects.create(
        default=default,
        library_entry=entry,
        text=question_text,
        fetch_status=fetch_status,
    )


def create_question_with_user_assigned(
    graphql_organization: Organization,
    question_text: str,
    answer_text: str,
    user_assigned: Union[User, None],
    completed: bool,
    default=False,
) -> Question:
    entry = create_library_entry(graphql_organization, answer_text)
    return Question.objects.create(
        default=default,
        library_entry=entry,
        text=question_text,
        user_assigned=user_assigned,
        completed=completed,
    )


def create_suggestion_questions(
    graphql_organization: Organization,
) -> Tuple[Question, Question]:
    equivalent_question_1 = create_question(
        graphql_organization, default=False, answer_text=EXISTING_QUESTION_ANSWER_TEXT
    )
    existing_suggestion_1 = create_question(graphql_organization)
    equivalent_question_2 = create_question(
        graphql_organization, default=False, answer_text=IMPORTED_QUESTION_ANSWER_TEXT
    )
    existing_suggestion_2 = create_question(graphql_organization)

    existing_question = create_question(
        graphql_organization,
        answer_text=EXISTING_QUESTION_ANSWER_TEXT,
        question_text=EXISTING_QUESTION_TEXT,
    )
    imported_question = create_question(
        graphql_organization,
        answer_text=IMPORTED_QUESTION_ANSWER_TEXT,
        question_text=IMPORTED_QUESTION_TEXT,
    )

    existing_question.equivalent_questions.add(equivalent_question_1)
    existing_question.equivalent_suggestions.add(
        *[existing_suggestion_1, imported_question]
    )

    imported_question.equivalent_questions.add(equivalent_question_2)
    imported_question.equivalent_suggestions.add(existing_suggestion_2)
    return existing_question, imported_question


def create_suggestion_alert(user: User, quantity: int):
    return LibraryEntrySuggestionsAlert.objects.custom_create(
        quantity=quantity,
        organization=user.organization,
        sender=user,
        receiver=user,
        alert_type=ALERT_TYPES['LIBRARY_ENTRY_SUGGESTIONS'],
    )

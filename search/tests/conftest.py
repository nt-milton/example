import pytest

from library.models import LibraryEntry, Question
from organization.models import Organization
from policy.models import Policy


@pytest.fixture
def published_policy(graphql_organization):
    return Policy.objects.create(
        organization=graphql_organization,
        name='Policy',
        category='Business Continuity & Disaster Recovery',
        description='testing',
        policy_text='testing content',
        is_published=True,
    )


@pytest.fixture
def not_published_policy(graphql_organization):
    return Policy.objects.create(
        organization=graphql_organization,
        name='Not published policy',
        category='Business Continuity & Disaster Recovery',
        description='not published testing',
        is_published=False,
    )


def create_library_entry(
    graphql_organization: Organization, answer_text='Search Answer text'
) -> LibraryEntry:
    return LibraryEntry.objects.create(
        organization=graphql_organization,
        answer_text=answer_text,
    )


def create_question(
    graphql_organization: Organization,
    answer_text='Search Answer text',
    question_text='Search Question text',
    default=True,
) -> Question:
    entry = create_library_entry(graphql_organization, answer_text)
    return Question.objects.create(
        default=default, library_entry=entry, text=question_text
    )


@pytest.fixture()
def question(graphql_organization: Organization) -> Question:
    return create_question(graphql_organization)


@pytest.fixture()
def default_question(graphql_organization: Organization) -> Question:
    return create_question(
        graphql_organization, question_text='Search default question text', default=True
    )

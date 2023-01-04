import pytest

from library.models import Question
from library.tests.factory import create_question
from organization.models import Organization


@pytest.fixture()
def default_question(graphql_organization: Organization) -> Question:
    return create_question(graphql_organization)

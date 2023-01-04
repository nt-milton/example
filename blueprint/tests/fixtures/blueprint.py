import json
from pathlib import Path

import pytest

from blueprint.constants import COMPLIANCE, HUMAN_RESOURCES, TECHNICAL
from laika.tests import mock_responses
from organization.models import OnboardingResponse
from pentest.tests.factory import load_response
from user.tests import create_user


@pytest.fixture
def get_typeform_result_response():
    response = load_response('typeform_response.json', path=Path(__file__).parents[1])
    with mock_responses([response]):
        yield json.loads(response)


@pytest.fixture
def get_typeform_result_response_himself_questions():
    response = load_response(
        'typeform_response_himself_questions.json', path=Path(__file__).parents[1]
    )
    with mock_responses([response]):
        yield json.loads(response)


@pytest.fixture
def onboarding_response(
    get_typeform_result_response, graphql_organization, graphql_user
) -> OnboardingResponse:
    return OnboardingResponse.objects.create(
        organization=graphql_organization,
        questionary_id='12992',
        response_id="201202",
        questionary_response=get_typeform_result_response,
        submitted_by=graphql_user,
    )


@pytest.fixture
def onboarding_response_himself_poc(
    get_typeform_result_response_himself_questions, graphql_organization, graphql_user
) -> OnboardingResponse:
    return OnboardingResponse.objects.create(
        organization=graphql_organization,
        questionary_id='12883',
        response_id="202930",
        questionary_response=get_typeform_result_response_himself_questions,
        submitted_by=graphql_user,
    )


@pytest.fixture
def suggested_owners(graphql_organization):
    return {
        COMPLIANCE: create_user(
            organization=graphql_organization, email='test+compliance@heylaika.com'
        ),
        HUMAN_RESOURCES: create_user(
            organization=graphql_organization, email='test+hr@heylaika.com'
        ),
        TECHNICAL: create_user(
            organization=graphql_organization, email='test+technical@heylaika.com'
        ),
    }

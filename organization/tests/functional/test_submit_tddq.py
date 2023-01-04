from unittest.mock import patch

import pytest

from organization.tests.mutations import SUBMIT_ONBOARDING_V2_FORM


@pytest.mark.functional(permissions=['organization.change_organization'])
@patch(
    'organization.mutations.get_typeform_answer_from_response',
    return_value=[{'field': {'ref': {'choices': {'labels': []}}}}],
)
def test_submit_typeform_questionnaire(typeform_response_mock, graphql_client):
    response = graphql_client.execute(
        SUBMIT_ONBOARDING_V2_FORM,
        variables={'responseId': 'qdvb8zrebels7hftdaqqdvb3dwfni3js'},
    )
    assert response is not None
    assert response.get('data') is not None
    assert response['data']['submitOnboardingV2Form']['success'] is True
    assert response['data']['submitOnboardingV2Form']['error'] is None


@pytest.mark.functional(permissions=['organization.change_organization'])
@patch('organization.mutations.get_typeform_answer_from_response', return_value=None)
def test_fail_submit_typeform_questionnaire(typeform_response_mock, graphql_client):
    response = graphql_client.execute(
        SUBMIT_ONBOARDING_V2_FORM,
        variables={'responseId': 'qdvb8zrebels7hftdaqqdvb3dwfni3js'},
    )
    assert response['data']['submitOnboardingV2Form']['success'] is False
    assert response['data']['submitOnboardingV2Form']['error'] is not None

import re
from unittest.mock import patch

import pytest

from control.tests import create_control
from organization.models import Organization
from policy.models import Policy
from search.utils import parsed_global_search, to_cmd_k_results
from user.models import User

COMMAND_K_QUERY = '''
query launchpadContext {
    launchpadContext {
        id
        context
        results {
            id
            name
            description
            url
        }
    }
}
'''


@pytest.fixture
def user():
    return User(organization=Organization())


@pytest.fixture(name="control")
def fixture_control(graphql_organization):
    return create_control(
        organization=graphql_organization,
        reference_id="CMD-001",
        display_id=1,
        name='Control Test',
        description="Control test description",
        implementation_notes='',
    )


@pytest.fixture
def policy():
    return Policy(
        name='Dummy Policy',
        organization=Organization(),
        is_published=True,
        policy_text='my policy search test',
    )


@pytest.mark.functional
@patch('concurrent.futures.ThreadPoolExecutor.map')
def test_cmd_k_search_controls(pool_map, user, control, policy):
    search_results = [
        {'result': [control, control], 'search_type': 'control'},
        {'result': [policy], 'search_type': 'policy'},
    ]
    pool_map.return_value = [search_results]

    formatted_results = parsed_global_search([], 'DUMMY TEXT', user)

    response = to_cmd_k_results(formatted_results)

    assert pool_map.called
    assert len(response) == 2

    control_result = response[0]
    assert "context" in control_result
    assert control_result["context"] == "control"
    assert "results" in control_result
    assert len(control_result["results"]) == 2
    assert control_result["results"][0]['id'] == control.id
    assert control_result["results"][0]['name'] == control.name

    policy_result = response[1]
    assert "context" in policy_result
    assert policy_result["context"] == "policy"
    assert "results" in policy_result
    assert policy_result["results"][0]['id'] == policy.id
    assert policy_result["results"][0]['name'] == policy.name


@pytest.mark.functional
def test_can_not_get_launchpad_response(graphql_client):
    response = graphql_client.execute(COMMAND_K_QUERY)
    assert 'errors' in response


@pytest.mark.functional(permissions=['dashboard.view_dashboard'])
@patch('concurrent.futures.ThreadPoolExecutor.map')
def test_can_get_launchpad_response(pool_map, graphql_client):
    pool_map.return_value = []
    response = graphql_client.execute(COMMAND_K_QUERY)
    assert 'errors' not in response


@pytest.mark.functional(permissions=['dashboard.view_dashboard'])
@patch('concurrent.futures.ThreadPoolExecutor.map')
def test_error_log(pool_map, caplog, graphql_client):
    pool_map.side_effect = [Exception('Something bad happened :)')]
    graphql_client.execute(COMMAND_K_QUERY)

    expected_log = r'ERROR\s+'
    assert re.search(expected_log, caplog.text)

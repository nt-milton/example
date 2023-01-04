import re
from concurrent.futures import TimeoutError
from unittest.mock import patch

import pytest

from control.tests import create_control
from organization.models import Organization
from policy.models import Policy
from search.search import get_launchpad_context, get_launchpad_results
from user.models import User
from vendor.models import OrganizationVendor


@pytest.fixture
def user():
    return User(organization=Organization())


@pytest.fixture(name="vendor")
def fixture_vendor(graphql_organization):
    return OrganizationVendor(organization=graphql_organization)


@pytest.fixture(name="control")
def fixture_control(graphql_organization, user):
    return create_control(
        organization=graphql_organization,
        reference_id="CMD-001",
        display_id=1,
        name='Control Test',
        description="Control test description",
        implementation_notes='',
    )


@pytest.fixture(name="policy")
def fixture_policy(graphql_organization):
    return Policy.objects.create(
        organization=graphql_organization,
        name='Policy',
        category='Business Continuity & Disaster Recovery',
        description='testing',
    )


@pytest.mark.functional
@patch('concurrent.futures.ThreadPoolExecutor.map')
def test_launchpad_context(pool_map, graphql_organization, control, policy, vendor):
    results = [
        {'results': [control], 'context': 'control'},
        {'results': [policy], 'context': 'policy'},
        {'results': [vendor], 'context': 'vendor'},
    ]
    pool_map.return_value = [results]

    response = get_launchpad_context(graphql_organization.id)

    control_result = response[0]
    assert "context" in control_result
    assert control_result["context"] == "control"
    assert "results" in control_result
    assert control_result["results"][0] == control

    policy_result = response[1]
    assert "context" in policy_result
    assert policy_result["context"] == "policy"
    assert "results" in policy_result
    assert policy_result["results"][0] == policy

    vendor_result = response[2]
    assert "context" in vendor_result
    assert vendor_result["context"] == "vendor"
    assert "results" in vendor_result
    assert vendor_result["results"][0] == vendor


@pytest.mark.functional
def test_performance_logs(caplog, graphql_organization):
    def mapper(model, organization_id):
        return model.objects.filter(organization_id=organization_id)

    provider = {'model': Policy, 'context': 'policy', 'mapper': mapper}
    get_launchpad_results(provider, graphql_organization.id)
    expected_logs = (
        r'INFO\s+.+Start running context: policy',
        r'INFO\s+.+Finish running context: policy \d+ ms',
    )
    for log_output in expected_logs:
        assert re.search(log_output, caplog.text)


@pytest.mark.functional
@patch('concurrent.futures.ThreadPoolExecutor.map')
def test_warning_logs(pool_map, caplog, graphql_organization):
    pool_map.side_effect = [TimeoutError()]
    get_launchpad_context(graphql_organization.id)

    expected_log = r'WARNING\s+.+get_launchpad_context timeout'
    assert re.search(expected_log, caplog.text)

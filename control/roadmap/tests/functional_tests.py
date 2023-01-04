import logging
import os

import pytest
from django.core.files import File

from certification.models import Certification, UnlockedOrganizationCertification
from control.models import Control
from control.roadmap.tests.queries import (
    GET_ALL_GROUPS,
    GET_BACKLOG_CONTROLS,
    GET_CONTROL_GROUPS,
)
from seeder.constants import DONE
from seeder.models import Seed

logger = logging.getLogger(__name__)
ROADMAP_SEED_FILE_PATH = f'{os.path.dirname(__file__)}/resources/groups_seed.zip'
controls = [
    'SOC 2 Security',
    'Data Security',
    'Risk & Threat Management',
    'Foundational Controls',
]


def execute_seed_for_roadmap(graphql_organization) -> Seed:
    seed_file = File(open(ROADMAP_SEED_FILE_PATH, 'rb'))
    return Seed.objects.create(
        organization=graphql_organization,
        seed_file=File(name='MySeedFile', file=seed_file),
    ).run(run_async=False, should_send_alerts=False)


@pytest.mark.functional(permissions=['control.view_roadmap'])
def test_control_groups_query(graphql_client, graphql_organization):
    execute_seed_for_roadmap(graphql_organization)
    soc2_security_framework = Certification.objects.get(name=controls[0])
    UnlockedOrganizationCertification.objects.create(
        organization=graphql_organization, certification=soc2_security_framework
    )

    executed = graphql_client.execute(
        GET_CONTROL_GROUPS, variables={'organizationId': graphql_organization.id}
    )

    data = executed['data']['groups']

    assert len(data) == 3
    assert data[0]['sortOrder'] == 1
    assert data[0]['name'] == controls[3]
    assert len(data[0]['controls']) == 3
    assert data[1]['sortOrder'] == 2
    assert data[1]['name'] == controls[1]
    assert len(data[1]['controls']) == 19
    assert data[2]['sortOrder'] == 3
    assert data[2]['name'] == controls[2]
    assert len(data[2]['controls']) == 21
    assert (
        data[0]['controls'][0]['allCertifications'][0]['displayName']
        == 'SOC 2 Security'
    )
    assert data[0]['controls'][0]['pillar']['name'] == 'Asset Managment'
    assert int(data[0]['controls'][0]['displayId']) == 1


@pytest.mark.functional(permissions=['control.view_roadmap'])
def test_control_groups_search_query(graphql_client, graphql_organization):
    updated_seed = execute_seed_for_roadmap(graphql_organization)
    controls = Control.objects.filter(organization_id=graphql_organization.id)

    assert updated_seed.status == DONE
    assert len(controls) == 55

    executed = graphql_client.execute(
        GET_CONTROL_GROUPS,
        variables={
            'organizationId': graphql_organization.id,
            'searchCriteria': 'Encryption',
        },
    )

    data = executed['data']['groups']
    amount_of_filtered_controls = 3

    assert len(data) > 0
    assert len(data[0]['controls']) == amount_of_filtered_controls


@pytest.mark.functional(permissions=['control.view_roadmap'])
def test_backlog_controls_query(graphql_client, graphql_organization):
    updated_seed = execute_seed_for_roadmap(graphql_organization)
    assert updated_seed.status == DONE

    executed = graphql_client.execute(
        GET_BACKLOG_CONTROLS, variables={'organizationId': graphql_organization.id}
    )

    amount_of_ungrouped_controls = 12
    data = executed['data']['backlog']

    assert len(data) == amount_of_ungrouped_controls


@pytest.mark.functional(permissions=['control.view_roadmap'])
def test_backlog_controls_search_query(graphql_client, graphql_organization):
    updated_seed = execute_seed_for_roadmap(graphql_organization)
    assert updated_seed.status == DONE

    executed = graphql_client.execute(
        GET_BACKLOG_CONTROLS,
        variables={'organizationId': graphql_organization.id, 'searchCriteria': 'data'},
    )

    amount_of_filtered_controls = 3
    data = executed['data']['backlog']

    assert len(data) == amount_of_filtered_controls


@pytest.mark.functional(permissions=['control.view_roadmap'])
def test_get_all_groups(graphql_client, graphql_organization):
    total_amount_groups = 3
    updated_seed = execute_seed_for_roadmap(graphql_organization)
    assert updated_seed.status == DONE

    executed = graphql_client.execute(
        GET_ALL_GROUPS, variables={'organizationId': graphql_organization.id}
    )

    data = executed['data']['allGroups']
    assert len(data) == total_amount_groups


@pytest.mark.functional(permissions=['control.view_roadmap'])
def test_filter_control_groups_by_framework(graphql_client, graphql_organization):
    execute_seed_for_roadmap(graphql_organization)
    soc2_security_framework = Certification.objects.get(name=controls[0])
    UnlockedOrganizationCertification.objects.create(
        organization=graphql_organization, certification=soc2_security_framework
    )

    executed = graphql_client.execute(
        GET_CONTROL_GROUPS,
        variables={
            'organizationId': graphql_organization.id,
            'searchCriteria': None,
            'filteredUnlockedFramework': '001',
        },
    )

    data = executed['data']['groups']

    assert len(data) == 3
    assert data[0]['sortOrder'] == 1
    assert data[0]['name'] == controls[3]
    assert len(data[0]['controls']) == 2
    assert data[1]['sortOrder'] == 2
    assert data[1]['name'] == controls[1]
    assert len(data[1]['controls']) == 4
    assert data[2]['sortOrder'] == 3
    assert data[2]['name'] == controls[2]
    assert len(data[2]['controls']) == 6


@pytest.mark.functional(permissions=['control.view_roadmap'])
def test_filter_control_groups_by_search_criteria(graphql_client, graphql_organization):
    execute_seed_for_roadmap(graphql_organization)
    soc2_security_framework = Certification.objects.get(name=controls[0])
    UnlockedOrganizationCertification.objects.create(
        organization=graphql_organization, certification=soc2_security_framework
    )

    executed = graphql_client.execute(
        GET_CONTROL_GROUPS,
        variables={
            'organizationId': graphql_organization.id,
            'searchCriteria': 'Security',
            'filteredUnlockedFramework': None,
        },
    )

    data = executed['data']['groups']

    assert len(data) == 2
    assert data[0]['sortOrder'] == 2
    assert data[0]['name'] == controls[1]
    assert len(data[1]['controls']) == 3
    assert data[1]['sortOrder'] == 3
    assert data[1]['name'] == controls[2]
    assert len(data[1]['controls']) == 3

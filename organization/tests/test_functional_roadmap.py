from datetime import datetime, timedelta

import pytest

from action_item.models import ActionItem, ActionItemStatus
from certification.models import (
    Certification,
    CertificationSection,
    UnlockedOrganizationCertification,
)
from certification.tests.factory import create_certification
from control.models import Control, ControlGroup, RoadMap
from control.tests.factory import create_action_item, create_control
from laika.utils.dates import YYYY_MM_DD
from organization.tests.queries import GET_ROADMAP, GET_ROADMAP_CONTROLS_SUMMARY


@pytest.fixture(autouse=True)
def set_up_test(graphql_user, graphql_organization):
    roadmap = RoadMap.objects.create(organization=graphql_organization)
    group = ControlGroup.objects.create(
        roadmap=roadmap,
        name="Group 1",
        reference_id=None,
        due_date=None,
        sort_order=1,
    )

    iso_cert_sections = ['iso3.1', 'iso4.1']
    soc_cert_sections = ['soc2.1', 'soc3.9']
    create_certification(
        graphql_organization,
        section_names=iso_cert_sections,
        name='ISO 27001',
        code='ISO',
    )
    create_certification(
        graphql_organization,
        section_names=soc_cert_sections,
        name='SOC 2 Type 1',
        code='SOC',
    )

    # Prepare control for roadmap group
    control = create_control(
        organization=graphql_organization,
        reference_id="CTR-001-SOC",
        name='Control Test',
        description='Control Test',
        display_id=1,
    )

    group.controls.add(control)

    for i in range(3):
        action_item = create_action_item(
            name=f"LAI-00{i}",
            description=f"Action item {i}",
            status="new",
            due_date=datetime.now() + timedelta(weeks=1),
            is_required=True,
        )
        control.action_items.add(action_item)
        action_item.assignees.add(graphql_user)

    # Prepare control for roadmap backlog
    control_2 = create_control(
        organization=graphql_organization,
        reference_id="CTR-002-ISO",
        name='Control Test 2',
        description='Control Test 2',
        display_id=2,
    )

    # Add certification sections to controls
    cert_section_1_iso = CertificationSection.objects.get(name=iso_cert_sections[0])
    cert_section_2_iso = CertificationSection.objects.get(name=iso_cert_sections[1])
    cert_section_1_soc = CertificationSection.objects.get(name=soc_cert_sections[0])
    cert_section_2_soc = CertificationSection.objects.get(name=soc_cert_sections[1])

    control_2.certification_sections.add(cert_section_1_iso, cert_section_2_iso)
    control.certification_sections.add(cert_section_1_soc, cert_section_2_soc)


@pytest.mark.functional(permissions=['control.view_roadmap'])
def test_get_roadmap_with_no_progress(
    graphql_client, graphql_organization, graphql_user
):
    # When
    response = graphql_client.execute(GET_ROADMAP)

    # Then
    roadmap = response['data']['roadmap']

    validate_roadmap(roadmap, progress=0)


@pytest.mark.functional(permissions=['control.view_roadmap'])
def test_get_roadmap_with_progress(graphql_client, graphql_organization, graphql_user):
    # Given
    control = Control.objects.get(reference_id="CTR-001-SOC")
    action_item = control.action_items.first()
    action_item.status = ActionItemStatus.COMPLETED
    action_item.save()

    # When
    response = graphql_client.execute(GET_ROADMAP)

    # Then
    roadmap = response['data']['roadmap']
    validate_roadmap(roadmap, progress=33)


@pytest.mark.functional(permissions=['control.view_roadmap'])
def test_get_roadmap_with_progress_when_not_applicable(
    graphql_client, graphql_organization, graphql_user
):
    # Given
    control = Control.objects.get(reference_id="CTR-001-SOC")
    action_item = control.action_items.first()
    action_item.status = ActionItemStatus.NOT_APPLICABLE
    action_item.save()

    # When
    response = graphql_client.execute(GET_ROADMAP)

    # Then
    roadmap = response['data']['roadmap']

    # Expected
    progress = 33

    group = roadmap['groups'][0]
    assert group['progress'] == progress


@pytest.mark.functional(permissions=['control.view_roadmap'])
def test_get_roadmap_completed(graphql_client, graphql_organization, graphql_user):
    # Given
    ActionItem.objects.filter(controls__reference_id="CTR-001-SOC").update(
        status=ActionItemStatus.COMPLETED
    )

    # When
    response = graphql_client.execute(GET_ROADMAP)

    # Then
    roadmap = response['data']['roadmap']

    assert not roadmap['completionDate']
    validate_roadmap(roadmap, progress=100)


@pytest.mark.functional(permissions=['control.view_roadmap'])
def test_get_roadmap_completed_when_not_applicable(
    graphql_client, graphql_organization, graphql_user
):
    # Given
    ActionItem.objects.filter(controls__reference_id="CTR-001-SOC").update(
        status=ActionItemStatus.NOT_APPLICABLE
    )

    # When
    response = graphql_client.execute(GET_ROADMAP)

    # Then
    roadmap = response['data']['roadmap']

    # Expected
    progress = 100

    group = roadmap['groups'][0]
    assert group['progress'] == progress


@pytest.mark.functional(permissions=['control.view_roadmap'])
def test_get_roadmap_groups_filtered_by_soc_certification(
    graphql_client, graphql_organization, graphql_user
):
    soc_certification = Certification.objects.filter(code='SOC').first()

    unlocked_cert = UnlockedOrganizationCertification.objects.get(
        organization=graphql_organization,
        certification=soc_certification,
    )

    today = datetime.now()
    unlocked_cert.target_audit_completion_date = today
    unlocked_cert.save()

    response = graphql_client.execute(
        GET_ROADMAP, variables={'filters': {'framework': str(soc_certification.id)}}
    )

    roadmap = response['data']['roadmap']
    roadmap_groups_controls = response['data']['roadmap']['groups'][0]['controls']
    roadmap_backlog = response['data']['roadmap']['backlog']

    assert roadmap
    assert roadmap['completionDate'] == today.strftime(YYYY_MM_DD)
    assert len(roadmap_groups_controls) == 1
    assert len(roadmap_backlog) == 0


@pytest.mark.functional(permissions=['control.view_roadmap'])
def test_get_roadmap_groups_filtered_by_iso_certification(
    graphql_client, graphql_organization, graphql_user
):
    iso_certification = Certification.objects.filter(code='ISO').first()

    response = graphql_client.execute(
        GET_ROADMAP, variables={'filters': {'framework': str(iso_certification.id)}}
    )

    roadmap_groups_controls = response['data']['roadmap']['groups'][0]['controls']
    roadmap_backlog = response['data']['roadmap']['backlog']

    assert len(roadmap_groups_controls) == 0
    assert len(roadmap_backlog) == 1


@pytest.mark.functional(permissions=['control.view_roadmap'])
def test_get_roadmap_controls_summary_for_iso_certification(graphql_client):
    iso_certification = Certification.objects.filter(code='ISO').first()

    response = graphql_client.execute(
        GET_ROADMAP_CONTROLS_SUMMARY,
        variables={'filters': {'framework': str(iso_certification.id)}},
    )

    implemented_controls = response['data']['roadmap']['implementedControls']
    total_controls = response['data']['roadmap']['totalControls']

    assert implemented_controls == 0
    assert total_controls == 1


def validate_roadmap(roadmap, progress):
    assert roadmap
    assert len(roadmap['groups']) == 1

    group = roadmap['groups'][0]
    assert group['progress'] == progress

    if progress == 100:
        assert not roadmap['completionDate']

    assert len(group['controls']) > 0
    assert group['controls'][0]['groupId']

    assert len(roadmap['backlog']) > 0
    backlog_control = roadmap['backlog'][0]
    assert backlog_control['health']
    assert backlog_control['groupId'] is None

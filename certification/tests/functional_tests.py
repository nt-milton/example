import logging

import pytest

from action_item.models import ActionItem, ActionItemStatus
from certification.constants import DEFAULT_CERTIFICATIONS
from certification.helpers import (
    get_certification_progress,
    get_required_action_items_completed,
    get_total_required_action_items,
)
from certification.models import (
    Certification,
    CertificationSection,
    UnlockedOrganizationCertification,
)
from certification.tests.factory import (
    create_certification as create_unlocked_certification_with_sections,
)
from certification.tests.factory import unlock_certification_for_organization
from certification.tests.queries import (
    GET_ALL_CERTIFICATES,
    GET_ALL_CERTIFICATION_LIST_BY_ORG,
    GET_CERTIFICATION_LIST,
    GET_CERTIFICATION_LIST_BY_ORG,
    GET_CERTIFICATIONS_FOR_PLAYBOOKS_MIGRATION,
    GET_MY_COMPLIANCE_CERTIFICATIONS,
    GET_UNLOCKED_CERTIFICATION_PROGRESS_PER_USER,
    UPDATE_UNLOCK_ORGANIZATION,
)
from control.models import Control, ControlCertificationSection
from control.tests.factory import create_control
from organization.tests import create_organization

logger = logging.getLogger(__name__)


def create_my_compliance_certifications():
    Certification.objects.create(
        name='SOC 1', code='S', airtable_record_id='12345a', is_visible=True
    )
    Certification.objects.create(
        name='SOC 2 Security',
        code='SOC-A',
        airtable_record_id='12345b',
        is_visible=True,
    )
    Certification.objects.create(
        name='SOC 2 Privacy', code='SOC-B', airtable_record_id='12345c', is_visible=True
    )
    Certification.objects.create(
        name='SOC 2 Availability',
        airtable_record_id='12345d',
        code='SOC-C',
        is_visible=True,
    )
    Certification.objects.create(
        name='PIPEDA', code='PIPEDA-A', airtable_record_id='12345e', is_visible=True
    )


def create_certifications():
    Certification.objects.create(name='my_cert', is_visible=True)
    Certification.objects.create(name='my_cert_2', is_visible=True)


def create_unlock_certification(organization):
    certification = Certification.objects.get(name='my_cert', is_visible=True)

    UnlockedOrganizationCertification.objects.create(
        organization=organization, certification=certification
    )


def create_certification(certification_name):
    certification = Certification.objects.create(name=certification_name)

    return certification


def create_control_certification_section(
    control_name, section_name, control_status, certification, organization
):
    certification_section, _ = CertificationSection.objects.get_or_create(
        name=section_name, certification_id=certification.id
    )

    control = create_control(
        organization=organization,
        name=control_name,
        display_id=1,
        status=control_status,
    )

    ControlCertificationSection.objects.create(
        certification_section_id=certification_section.id, control_id=control.id
    )


@pytest.fixture()
def certification_with_no_duplicated_action_items(
    _required_action_items,
    graphql_organization,
    graphql_user,
    _not_required_action_items,
):
    certification_name = 'ISO 27001 (2013)'
    certification_sections = ['ISO3.2', 'ISO3.4', 'ISO4.8.2', 'ISO1.4']
    create_unlocked_certification_with_sections(
        organization=graphql_organization,
        section_names=certification_sections,
        name=certification_name,
        unlock_certificate=True,
        code='ISO',
    )
    control_iso = create_control(
        graphql_organization,
        display_id='1',
        reference_id='AC-R-001-ISO',
        name='Control 1 ISO',
    )
    control_soc = create_control(
        graphql_organization,
        display_id='2',
        reference_id='AC-R-001-SOC',
        name='Control 1 SOC',
    )

    # Add certification sections to controls
    control_iso.certification_sections.add(
        *CertificationSection.objects.filter(name__in=certification_sections)
    )
    control_soc.certification_sections.add(
        *CertificationSection.objects.filter(name__in=certification_sections)
    )

    # Add action items to controls
    control_iso.action_items.add(*_required_action_items[:2])
    control_soc.action_items.add(*_required_action_items[2:])
    control_iso.action_items.add(*_not_required_action_items[:2])

    # Assign action items to user
    for required_ai, not_required_ai in zip(
        _required_action_items, _not_required_action_items
    ):
        required_ai.assignees.add(graphql_user)
        not_required_ai.assignees.add(graphql_user)
        required_ai.save()
        not_required_ai.save()

    # Complete one action item for iso control
    control_iso_ai_1 = ActionItem.objects.get(name='Required AI 1')
    control_iso_ai_1.status = ActionItemStatus.COMPLETED
    control_iso_ai_1.save()


@pytest.fixture()
def certification_with_duplicated_action_items(
    _required_action_items,
    graphql_organization,
    graphql_user,
    _not_required_action_items,
):
    certification_name_soc = 'SOC Security'
    certification_name_pipeda = 'PIPEDA'
    certification_sections_soc = ['ISO3.2', 'ISO3.4', 'ISO4.8.2', 'ISO1.4']
    certification_sections_pipeda = [
        'PIPEDA3.2',
        'PIPEDA3.4',
        'PIPEDA4.8.2',
        'PIPEDA1.4',
    ]

    create_unlocked_certification_with_sections(
        organization=graphql_organization,
        section_names=certification_sections_soc,
        name=certification_name_soc,
        unlock_certificate=True,
        code='SOC',
    )
    create_unlocked_certification_with_sections(
        organization=graphql_organization,
        section_names=certification_sections_pipeda,
        name=certification_name_pipeda,
        unlock_certificate=True,
        code='PIPEDA',
    )
    control_pipeda = create_control(
        graphql_organization,
        display_id='1',
        reference_id='AC-R-001-PIPEDA',
        name='Control 1 PIPEDA',
    )
    control_soc = create_control(
        graphql_organization,
        display_id='2',
        reference_id='AC-R-001-SOC',
        name='Control 1 SOC',
    )

    # Add certification sections to controls
    control_pipeda.certification_sections.add(
        *CertificationSection.objects.filter(name__in=certification_sections_pipeda)
    )
    control_soc.certification_sections.add(
        *CertificationSection.objects.filter(name__in=certification_sections_soc)
    )

    # Add action items to controls
    # first 2 required action items are in both pipeda and soc controls
    control_pipeda.action_items.add(*_required_action_items[:2])
    control_soc.action_items.add(*_required_action_items)
    control_soc.action_items.add(*_not_required_action_items)

    # Assign action items to user
    for required_ai, not_required_ai in zip(
        _required_action_items, _not_required_action_items
    ):
        required_ai.assignees.add(graphql_user)
        not_required_ai.assignees.add(graphql_user)
        required_ai.save()
        not_required_ai.save()

    # Complete first soc action item which is duplicated in pipeda control
    control_soc_ai_1 = ActionItem.objects.get(name='Required AI 1')
    control_soc_ai_1.status = ActionItemStatus.COMPLETED
    control_soc_ai_1.save()


@pytest.fixture(name='_required_action_items')
def fixture_required_action_items():
    return [
        ActionItem.objects.create(name='Required AI 1', is_required=True),
        ActionItem.objects.create(name='Required AI 2', is_required=True),
        ActionItem.objects.create(name='Required AI 3', is_required=True),
        ActionItem.objects.create(name='Required AI 4', is_required=True),
    ]


@pytest.fixture(name='_not_required_action_items')
def fixture_not_required_action_items():
    return [
        ActionItem.objects.create(name='Action item 1'),
        ActionItem.objects.create(name='Action item 2'),
        ActionItem.objects.create(name='Action item 3'),
        ActionItem.objects.create(name='Action item 4'),
    ]


@pytest.fixture(name='_certification_with_controls')
def fixture_certification_with_controls(
    graphql_organization, _required_action_items, _not_required_action_items
):
    certification = create_certification(DEFAULT_CERTIFICATIONS[0])
    certification.required_action_items = 4
    certification.save()
    create_control_certification_section(
        'Control 1', 'section_1', 'IMPLEMENTED', certification, graphql_organization
    )
    create_control_certification_section(
        'Control 2', 'section_1', 'IMPLEMENTED', certification, graphql_organization
    )

    control_1 = Control.objects.get(name='Control 1')
    control_2 = Control.objects.get(name='Control 2')

    control_1.action_items.add(*_required_action_items)
    control_1.action_items.add(*_not_required_action_items)
    control_2.action_items.add(*_required_action_items)
    return control_1, control_2


@pytest.fixture(name='_completed_action_items')
def fixture_completed_action_items():
    return [
        ActionItem.objects.create(
            name='Action item 1', status=ActionItemStatus.COMPLETED, is_required=True
        ),
        ActionItem.objects.create(
            name='Action item 2', status=ActionItemStatus.COMPLETED, is_required=True
        ),
        ActionItem.objects.create(
            name='Action item 3', status=ActionItemStatus.COMPLETED, is_required=True
        ),
        ActionItem.objects.create(
            name='Action item 4', status=ActionItemStatus.COMPLETED, is_required=True
        ),
    ]


@pytest.fixture(name='_not_applicable_action_items')
def fixture_not_applicable_action_items():
    return [
        ActionItem.objects.create(
            name='Action item 1',
            status=ActionItemStatus.NOT_APPLICABLE,
            is_required=True,
        ),
        ActionItem.objects.create(
            name='Action item 2',
            status=ActionItemStatus.NOT_APPLICABLE,
            is_required=True,
        ),
    ]


@pytest.mark.functional(permissions=['user.view_concierge'])
def test_resolve_certification_list(graphql_client):
    create_certifications()

    executed = graphql_client.execute(GET_CERTIFICATION_LIST)

    first_certification = executed['data']['certificationList'][0]
    second_certification = executed['data']['certificationList'][1]

    assert first_certification['id'] == '1'
    assert first_certification['name'] == 'my_cert'
    assert second_certification['id'] == '2'
    assert second_certification['name'] == 'my_cert_2'


@pytest.mark.functional(permissions=['user.view_concierge'])
def test_resolve_certifications_by_organization(graphql_client, graphql_organization):
    create_certifications()
    create_unlock_certification(graphql_organization)
    executed = graphql_client.execute(
        GET_CERTIFICATION_LIST_BY_ORG, variables={'id': str(graphql_organization.id)}
    )

    response = executed['data']['certificationsByOrganization']
    success = response['success']
    error = response['error']

    assert response['data'][0]['certification']['id'] == '1'
    assert success is True
    assert error is None


@pytest.mark.functional(permissions=['user.view_concierge'])
def test_resolve_compliance_certification_list(graphql_client):
    create_certifications()
    create_my_compliance_certifications()
    executed = graphql_client.execute(GET_MY_COMPLIANCE_CERTIFICATIONS)

    response = executed['data']['complianceCertificationList']

    TOTAL_COMPLIANCE_CERTIFICATIONS = 5

    assert len(response) == TOTAL_COMPLIANCE_CERTIFICATIONS


@pytest.mark.functional(permissions=['program.view_program'])
def test_resolve_all_certifications_by_organization(
    graphql_client, graphql_organization
):
    create_certifications()
    create_unlock_certification(graphql_organization)
    executed = graphql_client.execute(GET_ALL_CERTIFICATION_LIST_BY_ORG)

    response = executed['data']['allCertificationsByOrganization']
    success = response['success']
    error = response['error']

    assert response['data'][0]['certification']['id'] == '1'
    assert success is True
    assert error is None


@pytest.mark.functional(permissions=['user.change_concierge'])
def test_update_unlocked_org_certification_success(
    graphql_client, graphql_organization
):
    create_certifications()
    create_unlock_certification(graphql_organization)

    executed = graphql_client.execute(
        UPDATE_UNLOCK_ORGANIZATION,
        variables={
            'input': {
                'organizationId': graphql_organization.id,
                'certifications': [{'certificationId': '1', 'isUnlocking': False}],
            }
        },
    )

    response = executed['data']['updateUnlockCertification']
    success = response['success']
    error = response['error']

    assert success is True
    assert error is None


@pytest.mark.functional(permissions=['user.change_concierge'])
def test_update_unlocked_org_certification_toggle(graphql_client, graphql_organization):
    create_certifications()
    create_unlock_certification(graphql_organization)

    executed = graphql_client.execute(
        UPDATE_UNLOCK_ORGANIZATION,
        variables={
            'input': {
                'organizationId': graphql_organization.id,
                'certifications': [{'certificationId': '2', 'isUnlocking': True}],
            }
        },
    )

    response = executed['data']['updateUnlockCertification']
    success = response['success']
    error = response['error']

    assert success is True
    assert error is None


@pytest.mark.functional(permissions=['program.view_program'])
def test_certification_with_sections_shared_across_different_organizations(
    graphql_client, graphql_organization, _required_action_items
):
    certification = create_certification(DEFAULT_CERTIFICATIONS[0])
    certification.required_action_items = 4
    certification.save()
    create_control_certification_section(
        'Control 1', 'section_1', 'IMPLEMENTED', certification, graphql_organization
    )
    # Org 2 - validate edge case where:
    # control in different organizations share certification sections
    org2 = create_organization()
    create_control_certification_section(
        'Control 3', 'section_1', 'IMPLEMENTED', certification, org2
    )

    control_organization_1 = Control.objects.get(name='Control 1')
    control_organization_2 = Control.objects.get(name='Control 3')
    control_organization_1.action_items.add(*_required_action_items[:2])
    control_organization_2.action_items.add(*_required_action_items[2:4])
    _required_action_items[0].status = ActionItemStatus.COMPLETED
    _required_action_items[2].status = ActionItemStatus.COMPLETED
    _required_action_items[0].save()
    _required_action_items[2].save()

    executed = graphql_client.execute(GET_ALL_CERTIFICATES)

    locked_certifications = executed['data']['allCertificationList']

    assert locked_certifications[0]['progress'] == 25
    assert locked_certifications[0]['name'] == DEFAULT_CERTIFICATIONS[0]


@pytest.mark.functional(permissions=['program.view_program'])
def test_locked_certifications_with_required_action_items_empty_list(
    graphql_client, graphql_organization, _required_action_items
):
    certification = create_certification(DEFAULT_CERTIFICATIONS[1])
    certification.required_action_items = 4
    certification.save()
    unlock_certification_for_organization(graphql_organization, certification)
    create_control_certification_section(
        'Control 1', 'section_1', 'IMPLEMENTED', certification, graphql_organization
    )
    control_1 = Control.objects.get(name='Control 1')
    control_1.action_items.add(*_required_action_items)
    _required_action_items[0].status = ActionItemStatus.COMPLETED
    _required_action_items[0].save()

    executed = graphql_client.execute(GET_ALL_CERTIFICATES)

    locked_certifications = executed['data']['allCertificationList']
    assert len(locked_certifications) == 0


@pytest.mark.functional(permissions=['program.view_program'])
def test_certification_with_required_action_items_100progress(
    graphql_client,
    graphql_organization,
    _required_action_items,
    _certification_with_controls,
    _not_required_action_items,
):
    for ai in _required_action_items:
        ai.status = ActionItemStatus.COMPLETED
        ai.save()

    executed = graphql_client.execute(GET_ALL_CERTIFICATES)

    locked_certifications = executed['data']['allCertificationList']
    assert locked_certifications[0]['progress'] == 100
    assert locked_certifications[0]['name'] == DEFAULT_CERTIFICATIONS[0]


@pytest.mark.functional(permissions=['program.view_program'])
def test_certification_with_required_action_items_0progress(
    graphql_client, graphql_organization, _certification_with_controls
):
    executed = graphql_client.execute(GET_ALL_CERTIFICATES)

    locked_certifications = executed['data']['allCertificationList']
    assert locked_certifications[0]['progress'] == 0
    assert locked_certifications[0]['name'] == DEFAULT_CERTIFICATIONS[0]


@pytest.mark.functional(permissions=['program.view_program'])
def test_certification_with_shared_control_action_items_50progress(
    graphql_client, graphql_organization, _certification_with_controls
):
    control_1, control_2 = _certification_with_controls

    action_item_1 = control_1.action_items.filter(is_required=True).first()
    action_item_2 = control_2.action_items.exclude(pk=action_item_1.id).first()
    action_item_1.status = ActionItemStatus.COMPLETED
    action_item_2.status = ActionItemStatus.COMPLETED
    action_item_1.save()
    action_item_2.save()

    executed = graphql_client.execute(GET_ALL_CERTIFICATES)

    locked_certifications = executed['data']['allCertificationList']
    assert locked_certifications[0]['progress'] == 50
    assert locked_certifications[0]['name'] == DEFAULT_CERTIFICATIONS[0]


@pytest.mark.functional(permissions=['program.view_program'])
def test_certification_with_shared_control_action_items_75_progress(
    graphql_client, graphql_organization, _certification_with_controls
):
    control_1, control_2 = _certification_with_controls

    required_action_items = control_1.action_items.filter(is_required=True)
    action_item_1 = required_action_items.first()
    action_item_3 = required_action_items.last()
    action_item_2 = control_2.action_items.exclude(
        pk__in=[action_item_1.id, action_item_3.id]
    ).first()

    for ai in [action_item_1, action_item_2, action_item_3]:
        ai.status = ActionItemStatus.COMPLETED
        ai.save()

    executed = graphql_client.execute(GET_ALL_CERTIFICATES)

    locked_certifications = executed['data']['allCertificationList']
    assert locked_certifications[0]['progress'] == 75
    assert locked_certifications[0]['name'] == DEFAULT_CERTIFICATIONS[0]


@pytest.mark.functional(permissions=['program.view_program'])
def test_certification_with_zero_required_action_items_empty_list(
    graphql_client, graphql_organization, _required_action_items
):
    certification = create_certification(DEFAULT_CERTIFICATIONS[3])
    create_control_certification_section(
        'Control 1', 'section_1', 'IMPLEMENTED', certification, graphql_organization
    )
    control_1 = Control.objects.get(name='Control 1')
    control_1.action_items.add(*_required_action_items)
    required_ai_1 = _required_action_items[0]
    required_ai_1.status = ActionItemStatus.COMPLETED
    required_ai_1.save()

    executed = graphql_client.execute(GET_ALL_CERTIFICATES)

    locked_certifications = executed['data']['allCertificationList']
    assert len(locked_certifications) == 0


@pytest.mark.functional(permissions=['user.view_concierge'])
def test_resolve_certifications_for_playbooks_migration(graphql_client):
    create_certifications()
    create_my_compliance_certifications()
    executed = graphql_client.execute(GET_CERTIFICATIONS_FOR_PLAYBOOKS_MIGRATION)

    response = executed['data']['certificationsForPlaybooksMigration']

    total_certifications = 2

    assert len(response) == total_certifications
    assert response[0]['name'] == 'SOC 2 Availability'
    assert response[1]['name'] == 'SOC 2 Security'


@pytest.mark.parametrize(
    'certification_code, expected_progress', [('ISO', 50), ('SOC', 25)]
)
@pytest.mark.functional(permissions=['program.view_program'])
def test_unlocked_certification_progress_per_user(
    certification_code,
    expected_progress,
    graphql_client,
    certification_with_duplicated_action_items,
    certification_with_no_duplicated_action_items,
):
    certification = Certification.objects.get(code=certification_code)
    executed = graphql_client.execute(
        GET_UNLOCKED_CERTIFICATION_PROGRESS_PER_USER, variables={'id': certification.id}
    )
    certification_progress = executed['data']['unlockedCertificationProgressPerUser'][
        'progress'
    ]

    assert certification_progress == expected_progress


@pytest.mark.django_db
def test_get_total_required_action_items(_required_action_items):
    total_required_action_items = get_total_required_action_items(
        _required_action_items
    )
    assert total_required_action_items == 4


@pytest.mark.django_db
def test_get_required_action_items_completed(_completed_action_items):
    required_action_items_completed = get_required_action_items_completed(
        _completed_action_items
    )
    assert required_action_items_completed == 4


@pytest.mark.django_db
def test_get_required_action_items_not_applicable(_not_applicable_action_items):
    required_action_items_not_applicable = get_required_action_items_completed(
        _not_applicable_action_items
    )
    assert required_action_items_not_applicable == 2


@pytest.mark.django_db
def test_get_certification_progress(_completed_action_items):
    required_action_items_completed = get_required_action_items_completed(
        _completed_action_items
    )
    total_required_action_items = get_total_required_action_items(
        _completed_action_items
    )
    certification_progress = get_certification_progress(
        required_action_items_completed, total_required_action_items
    )
    assert certification_progress == 100


@pytest.mark.django_db
def test_get_certification_progress_negative(_required_action_items):
    """This test is to check that the certification_progress is not dividing by zero."""
    required_action_items_completed = get_required_action_items_completed(
        _required_action_items
    )
    total_required_action_items = get_total_required_action_items(
        _required_action_items
    )
    certification_progress = get_certification_progress(
        required_action_items_completed, total_required_action_items
    )
    assert certification_progress == 0

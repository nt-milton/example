from datetime import datetime
from unittest.mock import patch

import pytest

from action_item.models import ActionItem
from blueprint.admin.action_item import (
    set_action_item_tags as set_action_item_tags_blueprint,
)
from blueprint.constants import HUMAN_RESOURCES
from blueprint.models import TagBlueprint
from blueprint.models.control import ControlBlueprint
from blueprint.models.control_family import ControlFamilyBlueprint
from blueprint.models.control_group import ControlGroupBlueprint
from blueprint.prescribe import (
    get_family,
    get_or_create_group,
    get_or_create_org_control,
    prescribe_controls,
    set_action_item_tags,
    set_action_items,
    set_certification_sections,
    set_tags,
    unlock_frameworks,
)
from blueprint.tests.factory import create_action_item_blueprint, create_tag_blueprint
from blueprint.tests.mock_files.get_suggested_owners import get_suggested_owners
from certification.models import CertificationSection, UnlockedOrganizationCertification
from certification.tests.factory import create_certification
from control.models import Control, ControlGroup, ControlPillar, RoadMap
from control.roadmap.tests.factory import create_control_group
from control.tests.factory import (
    create_control,
    create_control_pillar,
    create_implementation_guide,
)
from tag.models import Tag

DATETIME_MOCK = datetime.strptime('2022-04-02T22:17:21.000Z', '%Y-%m-%dT%H:%M:%S.%f%z')


@pytest.fixture
def family_blueprint() -> ControlFamilyBlueprint:
    return ControlFamilyBlueprint.objects.create(
        name='Family',
        acronym='FM1',
        description='description',
        illustration='illustration',
    )


@pytest.fixture
def control_group_blueprint() -> ControlGroupBlueprint:
    return ControlGroupBlueprint.objects.create(
        name='Group 001',
        reference_id='GRP-001',
        sort_order=3,
        updated_at=datetime.strptime(
            '2022-04-02T22:17:21.000Z', '%Y-%m-%dT%H:%M:%S.%f%z'
        ),
    )


@pytest.fixture
def control_blueprint(family_blueprint) -> ControlBlueprint:
    return ControlBlueprint.objects.create(
        reference_id='AMG-001 (ISO)',
        household='AMG-001',
        name='Control blueprint',
        description='A description',
        family=family_blueprint,
        suggested_owner='Human Resources',
        display_id=5,
        framework_tag='SOC',
        implementation_guide=create_implementation_guide(
            name='New Implementation Guide', description='Any description'
        ),
        updated_at=datetime.strptime(
            '2022-03-02T22:20:15.000Z', '%Y-%m-%dT%H:%M:%S.%f%z'
        ),
    )


def create_tag(name, airtable_id, date):
    return TagBlueprint.objects.get_or_create(
        name=name, airtable_record_id=airtable_id, updated_at=date
    )


@pytest.fixture()
def tag_ai():
    return create_tag('Tag 001', '1234tag', DATETIME_MOCK)


@pytest.mark.django_db()
def test_prescribe_group(
    graphql_organization, control_group_blueprint, control_blueprint
):
    control_group_blueprint.controls.add(control_blueprint)

    # Prescribe
    roadmap = RoadMap.objects.create(organization_id=graphql_organization.id)
    get_or_create_group(control_blueprint, roadmap)

    org_control_group = ControlGroup.objects.first()
    assert ControlGroup.objects.count() == 1
    assert org_control_group.name == control_group_blueprint.name
    assert org_control_group.sort_order == control_group_blueprint.sort_order
    assert org_control_group.reference_id == control_group_blueprint.reference_id
    assert org_control_group.roadmap_id == roadmap.id


@pytest.mark.django_db()
def test_prescribe_family(control_blueprint, family_blueprint):
    # Prescribe
    get_family(control_blueprint)

    org_family = ControlPillar.objects.first()
    assert ControlPillar.objects.count() == 1
    assert org_family.name == family_blueprint.name
    assert org_family.acronym == family_blueprint.acronym
    assert org_family.description == family_blueprint.description
    assert org_family.illustration == family_blueprint.illustration


@pytest.mark.django_db()
def test_prescribe_control(
    graphql_organization, graphql_user, control_blueprint, suggested_owners
):
    roadmap = RoadMap.objects.create(organization_id=graphql_organization.id)

    org_control_group = create_control_group(
        roadmap, name='Group 007', reference_id='GRP-007'
    )

    org_control_family = create_control_pillar('Ctrl Family', acronym='CF1')

    # Prescribe
    org_control = get_or_create_org_control(
        control_blueprint,
        graphql_organization.id,
        org_control_group,
        org_control_family,
        suggested_owners,
    )

    assert Control.objects.count() == 1
    assert org_control == Control.objects.first()
    assert org_control.organization_id == graphql_organization.id
    assert org_control.reference_id == control_blueprint.reference_id
    assert org_control.household == control_blueprint.household
    assert org_control.name == control_blueprint.name
    assert org_control.description == control_blueprint.description
    assert org_control.status == control_blueprint.status
    assert org_control.pillar == org_control_family
    assert org_control.owner1 == suggested_owners[HUMAN_RESOURCES]
    assert org_control.display_id == control_blueprint.display_id
    assert org_control.framework_tag == control_blueprint.framework_tag
    assert (
        org_control.implementation_guide_blueprint
        == control_blueprint.implementation_guide
    )
    assert org_control.group.first() == org_control_group


@pytest.mark.django_db()
def test_prescribe_set_action_items(
    graphql_user, graphql_organization, control_blueprint, suggested_owners
):
    action_item_blueprint_1 = create_action_item_blueprint()
    action_item_blueprint_2 = create_action_item_blueprint()
    control_blueprint.action_items.set(
        [
            action_item_blueprint_1,
            action_item_blueprint_2,
        ]
    )

    org_control = create_control(graphql_organization, 1, 'Org Control')

    org_action_item_1 = ActionItem.objects.create(
        name=action_item_blueprint_1.name,
        description=action_item_blueprint_1.description,
        is_required=action_item_blueprint_1.is_required,
        is_recurrent=action_item_blueprint_1.is_recurrent,
        metadata={
            'referenceId': action_item_blueprint_1.reference_id,
            'organizationId': graphql_organization.id.hex,
        },
    )

    org_action_item_2 = ActionItem.objects.create(
        name=action_item_blueprint_1.name,
        description=action_item_blueprint_1.description,
        is_required=action_item_blueprint_1.is_required,
        is_recurrent=action_item_blueprint_1.is_recurrent,
        metadata={
            'referenceId': action_item_blueprint_1.reference_id,
            'organizationId': graphql_organization.id.hex,
        },
    )

    org_control.action_items.set([org_action_item_1, org_action_item_2])

    # Prescribe
    set_action_items(
        control_blueprint, graphql_organization.id.hex, org_control, suggested_owners
    )

    # Assert
    assert_action_item = org_control.action_items.filter(
        metadata__referenceId=action_item_blueprint_2.reference_id
    ).first()

    assert org_control.action_items.exists()
    assert org_control.action_items.count() == 3
    assert assert_action_item.name == action_item_blueprint_2.name
    assert assert_action_item.description == action_item_blueprint_2.description
    assert assert_action_item.is_required == action_item_blueprint_2.is_required
    assert assert_action_item.is_recurrent == action_item_blueprint_2.is_recurrent
    assert assert_action_item.assignees.count() == 1
    assert assert_action_item.display_id == action_item_blueprint_2.display_id
    assert (
        assert_action_item.recurrent_schedule
        == action_item_blueprint_2.recurrent_schedule
    )


@pytest.mark.django_db()
def test_prescribe_set_tags(graphql_organization, control_blueprint):
    tag_blueprint_1 = create_tag_blueprint(name='Tag001')
    tag_blueprint_2 = create_tag_blueprint(name='Tag002')
    control_blueprint.tags.set([tag_blueprint_1, tag_blueprint_2])

    org_control = create_control(graphql_organization, 1, 'Org Control')

    # Prescribe
    set_tags(control_blueprint, graphql_organization.id, org_control)

    first_tag = Tag.objects.first()
    assert Tag.objects.count() == 2
    assert first_tag.name == tag_blueprint_1.name


@pytest.mark.django_db()
def test_prescribe_set_action_item_tags(graphql_organization, tag_ai):
    action_item_blueprint = create_action_item_blueprint()

    defaults = {
        'name': action_item_blueprint.name,
        'description': action_item_blueprint.description,
        'is_required': action_item_blueprint.is_required,
        'is_recurrent': action_item_blueprint.is_recurrent,
        'recurrent_schedule': action_item_blueprint.recurrent_schedule,
        'display_id': action_item_blueprint.display_id,
    }
    org_action_item = ActionItem.objects.create(**defaults)

    fields = {'Tags': ['1234tag']}
    set_action_item_tags_blueprint(action_item_blueprint, fields)

    # Prescribe
    set_action_item_tags(
        action_item_blueprint, graphql_organization.id, org_action_item
    )

    current_action_item = ActionItem.objects.all().first()
    current_action_item_tags = current_action_item.tags.all()

    assert current_action_item_tags[0].name == 'Tag 001'
    assert len(current_action_item_tags) == 1


@pytest.mark.django_db()
def test_prescribe_set_certification_sections(graphql_organization, control_blueprint):
    soc_2 = create_certification(
        graphql_organization, ['cs1', 'cs3'], name='SOC 2 TYPE 2'
    )

    control_blueprint.certification_sections.set(soc_2.sections.all())

    org_control = create_control(graphql_organization, 1, 'Org Control')

    # Prescribe
    set_certification_sections(control_blueprint, org_control)

    org_control_sections_set = set(org_control.certification_sections.all())
    blueprint_control_sections_set = set(control_blueprint.certification_sections.all())

    assert CertificationSection.objects.count() == 2
    assert org_control.certification_sections.exists()
    assert org_control_sections_set == blueprint_control_sections_set


@patch('blueprint.prescribe.get_suggested_users')
@pytest.mark.django_db()
def test_prescribe_controls(
    get_suggested_users_mock,
    graphql_organization,
    control_group_blueprint,
    control_blueprint,
    onboarding_response,
):
    get_suggested_users_mock.return_value = get_suggested_owners(graphql_organization)
    action_item_blueprint_1 = create_action_item_blueprint()
    tag_blueprint_1 = create_tag_blueprint(name='Tag001')
    soc_2_certificate = create_certification(
        graphql_organization, ['cs100'], name='SOC 2 TYPE 2'
    )

    control_group_blueprint.controls.add(control_blueprint)
    control_blueprint.action_items.add(action_item_blueprint_1)
    control_blueprint.tags.set([tag_blueprint_1])
    control_blueprint.certification_sections.set(soc_2_certificate.sections.all())

    prescribe_controls(graphql_organization.id.hex, [control_blueprint.reference_id])
    get_suggested_users_mock.assert_called_once()

    org_control = Control.objects.first()
    assert Control.objects.count() == 1
    assert CertificationSection.objects.count() == 1
    assert org_control.group.exists()
    assert org_control.implementation_guide_blueprint
    assert org_control.tags.exists()
    assert org_control.action_items.exists()
    assert org_control.certification_sections.exists()


@pytest.mark.django_db()
def test_prescribe_unlock_frameworks(graphql_organization, control_blueprint):
    expected_cert = 'GDPR'
    gdpr_certificate = create_certification(
        graphql_organization, [expected_cert], name=expected_cert
    )
    control_blueprint.certification_sections.set(gdpr_certificate.sections.all())
    control_blueprint.framework_tag = expected_cert

    controls = ControlBlueprint.objects.all()

    unlock_frameworks(controls, graphql_organization.id)
    unlocked_frameworks = UnlockedOrganizationCertification.objects.filter(
        organization_id=graphql_organization.id
    )

    assert len(unlocked_frameworks) == 1
    assert unlocked_frameworks[0].certification.name == expected_cert

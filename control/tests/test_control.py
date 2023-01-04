import pytest

from blueprint.models import ImplementationGuideBlueprint
from certification.models import Certification, CertificationSection
from control.admin import ControlForm
from control.helpers import get_health_stats
from control.models import Control, ControlGroup, ControlPillar, RoadMap
from control.schema import set_order
from control.tests.factory import create_control
from organization.models import Organization
from organization.tests.factory import create_organization
from tag.models import Tag


@pytest.fixture(autouse=True)
def organization():
    return create_organization(flags=[], name='Test Org')


def create_default_control(name='Test Control 1') -> Control:
    organization = Organization.objects.first()
    return Control.objects.create(organization=organization, name=name)


@pytest.mark.django_db
def test_control_previous_is_none():
    control = create_default_control()
    assert control.previous is None


@pytest.mark.django_db
def test_control_next_is_none():
    control = create_default_control()
    assert control.next is None


@pytest.mark.django_db
def test_control_position_is_1():
    control = create_default_control()
    assert control.position == 1


@pytest.mark.django_db
def test_control_has_next():
    control1 = create_default_control()
    control2 = create_default_control(name='control 2')
    assert control1.next == control2


@pytest.mark.django_db
def test_control_position_2_has_previous():
    control1 = create_default_control()
    control2 = create_default_control(name='position 2')
    assert control2.position == 2
    assert control2.previous == control1


@pytest.mark.django_db
def test_control_position_2_has_next_and_previous():
    control1 = create_default_control()
    control2 = create_default_control(name='pos2')
    control3 = create_default_control(name='pos3')
    assert control2.previous == control1
    assert control2.next == control3


@pytest.mark.django_db
def test_control_previous_of_next_is_the_same_as_current():
    control1 = create_default_control()
    create_default_control(name='pos2')
    prev_of_next = control1.next.previous
    assert prev_of_next == control1


@pytest.mark.django_db
def test_control_next_of_previous_is_the_same_as_current():
    create_default_control()
    control2 = create_default_control(name='pos2')
    prev_of_next = control2.previous.next
    assert prev_of_next == control2


@pytest.mark.django_db
def test_control_position_3_has_prev_position_2_and_next_position_4():
    """
    Create 5 control
    test control with display 3 has previous
    with display 2 and next with display 4
    """
    for idx in range(5):
        create_control(
            organization=Organization.objects.first(),
            name=f'Control with idx {idx}',
            display_id=idx,
            reference_id=None,
        )

    control: Control = Control.objects.get(display_id=3)

    assert control.previous.display_id == 2
    assert control.next.display_id == 4


@pytest.mark.django_db
def test_control_next_previous_control_with_reference_id_next_without_it():
    control_with_reference_id = create_control(
        organization=Organization.objects.first(),
        name='Control with reference id',
        reference_id='AB-003',
        display_id=1,
    )
    control_without_reference_id = create_control(
        organization=Organization.objects.first(),
        name='Control without reference id',
        reference_id=None,
        display_id=2,
    )
    assert control_with_reference_id.next.id == control_without_reference_id.id
    assert control_without_reference_id.previous.id == control_with_reference_id.id


@pytest.mark.django_db
def test_set_order():
    """
    Test set_order function for sorting controls data
    """

    class DummyControl:
        def __init__(self, id, health):
            self.id = id
            self.health = health

    control_list = [
        DummyControl(id='id1', health='NOT_IMPLEMENTED'),
        DummyControl(id='id2', health='FLAGGED'),
        DummyControl(id='id3', health='NO_DATA'),
        DummyControl(id='id4', health='HEALTHY'),
        DummyControl(id='id5', health='NO_MONITORS'),
    ]

    controls_health = {
        'id1': 'NOT_IMPLEMENTED',
        'id2': 'FLAGGED',
        'id3': 'NO_DATA',
        'id4': 'HEALTHY',
        'id5': 'NO_MONITORS',
    }

    data = sorted(control_list, key=set_order(controls_health))

    assert data[0].health == 'FLAGGED'
    assert data[1].health == 'NO_DATA'
    assert data[2].health == 'NOT_IMPLEMENTED'
    assert data[3].health == 'NO_MONITORS'
    assert data[4].health == 'HEALTHY'


@pytest.mark.django_db
def test_get_stats_controls_by_health():
    controls_health = {
        "1": "HEALTHY",
        "2": "FLAGGED",
        "3": "NO_DATA",
        "4": "HEALTHY",
        "5": "FLAGGED",
        "6": "NO_DATA",
        "7": "HEALTHY",
        "8": "NO_DATA",
        "9": "NO_DATA",
        "10": "HEALTHY",
        "11": "HEALTHY",
        "12": "HEALTHY",
        "13": "NO_MONITORS",
        "14": "NOT_IMPLEMENTED",
    }

    expected_stats = {
        'healthy': 6,
        'flagged': 2,
        'no_data': 4,
        'no_monitors': 1,
        'not_implemented': 1,
    }

    assert get_health_stats(controls_health) == expected_stats


@pytest.mark.django_db
def test_m2m_fields_control_form_new_control(organization):
    """
    Test the creation and saving on many to many
    fields for control form on django admin
    """
    name = 'control form test'
    certification = Certification.objects.create(name='cert test')
    cert_sect = CertificationSection.objects.create(
        name='cert sect test', certification=certification
    )
    tag = Tag.objects.create(name='test tag', organization=organization)
    pillar = ControlPillar.objects.create(name='Asset Management')
    implementation_guide = ImplementationGuideBlueprint.objects.create(
        name='Imp guide test', description='Any description'
    )

    mandatory_fields = {
        'id': 'e4e231d6-00cc-4620-8bc2-cd8bb416ff68',
        'name': name,
        'organization': organization,
        'display_id': 1,
        'pillar': pillar,
        'implementation_guide_blueprint': implementation_guide,
        'certification_sections': [cert_sect],
        'tags': [tag],
    }

    control_form = ControlForm(mandatory_fields)
    control = control_form.save()

    assert control.name == name
    assert control.organization == organization
    assert control.pillar == pillar
    assert implementation_guide == implementation_guide
    assert control.tags.first() == tag
    assert control.certification_sections.first() == cert_sect


@pytest.mark.django_db
def test_create_control_group(organization):
    first_order = 1
    second_order = 3

    roadmap = RoadMap.objects.create(organization_id=organization.id)

    first_group = ControlGroup.objects.create(roadmap=roadmap, name='First Group')
    second_group = ControlGroup.objects.create(
        roadmap=roadmap, name='Second Group', sort_order=second_order
    )
    third_group = ControlGroup.objects.create(roadmap=roadmap, name='Third Group')

    assert first_group and first_group.sort_order == first_order
    assert second_group and second_group.sort_order == second_order
    assert third_group and third_group.sort_order == second_order + 1

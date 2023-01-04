import pytest

from control.models import ControlPillar
from control.tests import create_control

from .queries import GET_CONTROLS_PER_FAMILY


def associate_controls_to_pillar(pillar, controls, organization, user):
    display_id = 0
    for control in controls:
        create_control(
            organization=organization,
            display_id=display_id + 1,
            reference_id='XX-' + str(display_id + 1),
            name=control,
            pillar=pillar,
            owner1=user,
            description='Test Description ' + str(display_id + 1),
        )
        display_id += 1


@pytest.fixture(name='_controls_pillars')
def fixture_create_pillars_with_controls_associated(graphql_organization, graphql_user):
    pillar_names = ['Pillar 1', 'Pillar 2', 'Pillar 3', 'Pillar 4']
    controls_per_pillar = {
        'Pillar 1': ['Control 1', 'Control 2', 'Control 3', 'Control 4'],
        'Pillar 2': ['Control 1.2', 'Control 2.2', 'Control 3.2'],
        'Pillar 3': ['Control 1.3', 'Control 2.3'],
        'Pillar 4': ['Control 1.4'],
    }
    control_pillars = [
        ControlPillar.objects.create(name=pillar, acronym='CP')
        for pillar in pillar_names
    ]

    for pillar in control_pillars:
        controls = controls_per_pillar.get(pillar.name)
        associate_controls_to_pillar(
            pillar, controls, graphql_organization, graphql_user
        )

    return control_pillars


@pytest.fixture(name='_controls_pillars_unordered')
def fixture_create_pillars_with_controls_associated_unordered(
    graphql_organization, graphql_user
):
    pillar_names = [
        {'name': 'Pillar 1', 'id': 3},
        {'name': 'Pillar 2', 'id': 7},
        {'name': 'Pillar 3', 'id': 1},
        {'name': 'Pillar 4', 'id': 10},
    ]
    controls_per_pillar = {
        'Pillar 2': ['Control 1.4'],
        'Pillar 4': ['Control 1.2', 'Control 2.2', 'Control 3.2'],
        'Pillar 3': ['Control 1.3', 'Control 2.3'],
        'Pillar 1': ['Control 1', 'Control 2', 'Control 3', 'Control 4'],
    }
    control_pillars = [
        ControlPillar.objects.create(name=pillar['name'], id=pillar['id'])
        for pillar in pillar_names
    ]

    for pillar in control_pillars:
        controls = controls_per_pillar.get(pillar.name)
        associate_controls_to_pillar(
            pillar, controls, graphql_organization, graphql_user
        )

    return control_pillars


@pytest.mark.functional(permissions=['control.view_control'])
def test_get_roadmap_overview_controls_families(
    graphql_client, graphql_user, _controls_pillars
):
    response = graphql_client.execute(GET_CONTROLS_PER_FAMILY)

    controls_per_family = response['data']['controlsPerFamily']
    family_1 = [
        family
        for family in controls_per_family
        if family['familyName'] == _controls_pillars[0].full_name
    ][0]
    family_1_control = family_1['familyControls'][0]

    assert len(_controls_pillars) == len(controls_per_family)
    assert len(family_1['familyControls']) == 4
    assert family_1['familyName'] == 'CP: Pillar 1'
    assert family_1_control['ownerDetails'][0]['id'] == str(graphql_user.id)
    assert family_1_control['description'] == 'Test Description 1'


@pytest.mark.functional(permissions=['control.view_control'])
def test_get_roadmap_overview_controls_families_ordering(
    graphql_client, _controls_pillars_unordered
):
    response = graphql_client.execute(GET_CONTROLS_PER_FAMILY)

    controls_per_family = response['data']['controlsPerFamily']
    first_family = [
        family
        for family in controls_per_family
        if family['familyName'] == _controls_pillars_unordered[2].name
    ][0]
    last_family = [
        family
        for family in controls_per_family
        if family['familyName'] == _controls_pillars_unordered[3].name
    ][0]

    first_family_control_1 = first_family['familyControls'][0]
    last_family_control_1 = last_family['familyControls'][0]

    assert first_family['familyName'] == 'Pillar 3'
    assert last_family['familyName'] == 'Pillar 4'
    assert first_family_control_1['name'] == 'Control 1.3'
    assert last_family_control_1['name'] == 'Control 1.2'

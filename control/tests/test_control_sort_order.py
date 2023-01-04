import pytest

from control.models import ControlGroup, RoadMap

FIRST_ORDER = 1
SECOND_ORDER = 2
THIRD_ORDER = 3


@pytest.fixture()
def roadmap(graphql_organization):
    return RoadMap.objects.create(organization=graphql_organization)


@pytest.fixture()
def create_groups(roadmap):
    first_group = ControlGroup.objects.create(
        name='Fake Name 1',
        reference_id='some-reference-id-1',
        roadmap_id=roadmap.id,
    )
    second_group = ControlGroup.objects.create(
        name='Fake Name 2',
        reference_id='some-reference-id-2',
        roadmap_id=roadmap.id,
    )

    return first_group, second_group


@pytest.mark.functional()
def test_control_groups_order_with_no_groups(create_groups):
    first_group, second_group = create_groups

    assert first_group.sort_order == FIRST_ORDER
    assert second_group.sort_order == SECOND_ORDER


@pytest.mark.functional()
def test_control_groups_order_with_groups(roadmap, create_groups):
    first_group, second_group = create_groups
    third_group = ControlGroup.objects.create(
        name='Fake Name 3',
        reference_id='some-reference-id-3',
        roadmap_id=roadmap.id,
    )

    assert first_group.sort_order == FIRST_ORDER
    assert second_group.sort_order == SECOND_ORDER
    assert third_group.sort_order == THIRD_ORDER

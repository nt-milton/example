import pytest
from django.utils.timezone import now

from action_item.launchpad import launchpad_mapper
from action_item.models import ActionItem
from control.tests.factory import create_action_item, create_control
from organization.tests import create_organization


@pytest.mark.django_db
def test_action_item_launchpad_mapper(graphql_organization, graphql_user):
    due_date = now()
    control_one = create_control(
        organization=graphql_organization,
        display_id=1,
        name='Action One',
        reference_id='CO-01',
    )

    action_item_one = create_action_item(
        name='Action item One',
        description='Action item description',
        due_date=due_date,
        metadata={
            'referenceId': 'LAI-001',
            'organizationId': str(graphql_organization.id),
        },
    )

    action_item_two = create_action_item(
        name='Action item Two',
        description='Action item description',
        metadata={
            'referenceId': 'LAI-002',
            'organizationId': str(graphql_organization.id),
        },
    )

    test_organization = create_organization(flags=[], name='Test Org')

    control_two = create_control(
        organization=test_organization,
        display_id=2,
        name='Action Two',
        reference_id='CO-02',
    )

    action_item_three = create_action_item(
        name='Action item Three',
        description='Action item description',
        due_date=due_date,
        metadata={
            'referenceId': 'LAI-003',
            'organizationId': str(test_organization.id),
        },
    )

    control_one.action_items.add(action_item_one)
    control_one.action_items.add(action_item_two)
    control_two.action_items.add(action_item_three)

    action_items = launchpad_mapper(ActionItem, graphql_organization.id)

    assert len(action_items) == 2

    assert action_items[0].id == f"{control_one.id}-{action_item_one.id}"
    assert action_items[0].name == 'Action item One'
    assert action_items[0].description == 'Action item description'
    assert action_items[0].control == 'CO-01'
    assert action_items[0].reference_id == 'LAI-001'
    assert action_items[0].due_date == due_date.strftime('%m/%d/%Y')
    assert action_items[0].url == f"/controls/{control_one.id}"

    assert action_items[1].id == f"{control_one.id}-{action_item_two.id}"
    assert action_items[1].name == 'Action item Two'
    assert action_items[1].description == 'Action item description'
    assert action_items[1].control == 'CO-01'
    assert action_items[1].reference_id == 'LAI-002'
    assert not action_items[1].due_date
    assert action_items[1].url == f"/controls/{control_one.id}"

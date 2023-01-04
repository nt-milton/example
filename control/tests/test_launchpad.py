import pytest

from control.models import Control
from control.tests import create_control
from control.utils import launchpad


@pytest.fixture
def control(graphql_organization):
    return create_control(
        organization=graphql_organization,
        reference_id="AMG-001",
        display_id=1,
        name='Control name',
        description='Control description',
        implementation_notes='',
    )


@pytest.mark.django_db
def test_control_mapper(control, graphql_organization):
    controls = launchpad.launchpad_mapper(Control, graphql_organization.id)
    control_context = controls[0]

    assert control_context.id == control.id
    assert control_context.name == control.name
    assert control_context.reference_id == 'AMG-001'
    assert control_context.description == 'Control description'
    assert control_context.url == f"/controls/{control.id}"

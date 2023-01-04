import pytest
from django.utils import timezone

from control.constants import STATUS
from control.models import Control
from control.tests.factory import create_control
from control.tests.mutations import UPDATE_CONTROL_STATUS


@pytest.fixture(name='_current_date')
def fixture_current_date():
    return timezone.now()


@pytest.fixture(name='_yesterdays_date')
def fixture_yesterdays_date():
    return timezone.now() - timezone.timedelta(days=1)


@pytest.fixture(name="_control_not_implemented")
def fixture_control_not_implemented(graphql_organization):
    return create_control(
        organization=graphql_organization,
        reference_id="AMG-001",
        display_id=1,
        name='Control Test 1',
        status=STATUS['NOT IMPLEMENTED'],
        implementation_date=None,
    )


@pytest.fixture(name="_control_implemented")
def fixture_control_implemented(graphql_organization, _yesterdays_date):
    return create_control(
        organization=graphql_organization,
        reference_id="AMG-002",
        display_id=2,
        name='Control Test 2',
        status=STATUS['IMPLEMENTED'],
        implementation_date=_yesterdays_date,
    )


@pytest.mark.functional(permissions=['control.change_control'])
def test_implementation_date_for_not_implemented_control(
    graphql_client, _control_not_implemented, _current_date
):
    variables = {
        'input': {
            'id': str(_control_not_implemented.id),
            'status': 'implemented',
        }
    }

    graphql_client.execute(UPDATE_CONTROL_STATUS, variables=variables)
    control = Control.objects.get(id=_control_not_implemented.id)

    assert control.implementation_date.replace(
        second=0, microsecond=0
    ) == _current_date.replace(second=0, microsecond=0)


@pytest.mark.functional(permissions=['control.change_control'])
def test_not_implemented_changes_implementation_date_to_none(
    graphql_client, _control_implemented
):
    variables = {
        'input': {
            'id': str(_control_implemented.id),
            'status': 'not implemented',
        }
    }

    graphql_client.execute(UPDATE_CONTROL_STATUS, variables=variables)

    control = Control.objects.get(id=_control_implemented.id)
    assert control.implementation_date is None


@pytest.mark.functional(permissions=['control.change_control'])
def test_changing_other_field_does_not_changes_implementation_date(
    graphql_client, _control_implemented, _yesterdays_date
):
    variables = {
        'input': {
            'id': str(_control_implemented.id),
            'description': 'test description',
            'name': 'test name',
        }
    }

    graphql_client.execute(UPDATE_CONTROL_STATUS, variables=variables)

    control = Control.objects.get(id=_control_implemented.id)
    assert control.implementation_date == _yesterdays_date


@pytest.mark.functional(permissions=['control.change_control'])
def test_implemented_control_does_not_changes_implementation_date(
    graphql_client, _control_implemented, _yesterdays_date
):
    variables = {'input': {'id': str(_control_implemented.id), 'status': 'implemented'}}

    graphql_client.execute(UPDATE_CONTROL_STATUS, variables=variables)

    control = Control.objects.get(id=_control_implemented.id)
    assert control.implementation_date == _yesterdays_date

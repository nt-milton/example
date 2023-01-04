import pytest

from action_item.models import ActionItem
from control.models import Control
from organization.models import Organization
from organization.tasks import delete_aws_data
from organization.tests.test_utils import disconnect_org_and_seeder_post_savings


@pytest.mark.django_db
def test_delete_org(graphql_user):
    disconnect_org_and_seeder_post_savings()

    organization = Organization.objects.create(
        name='To delete', website='https://fake.org'
    )
    organization_id = organization.id

    Control.objects.create(name='Control 0', organization_id=organization_id)
    ActionItem.objects.create(name='Action 1').controls.add(
        Control.objects.create(name='Control 1', organization_id=organization_id)
    )

    organization.delete()
    response = delete_aws_data('UUID')

    assert response.get('success')
    assert not Organization.objects.filter(id=organization_id).first()
    assert not Control.objects.filter(organization_id=organization_id)

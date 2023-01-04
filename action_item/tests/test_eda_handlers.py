from datetime import datetime

import pytest

from action_item.edas_handler import on_create_payroll_connection_account_handler
from action_item.models import ActionItem, ActionItemStatus
from integration.constants import ACTION_ITEM_FOR_PAYROLL_INTEGRATION


@pytest.mark.django_db
def test_on_create_connection_account_bad_message():
    response = on_create_payroll_connection_account_handler({})
    assert not response


@pytest.mark.django_db
def test_on_create_connection_account_success(graphql_organization):
    ActionItem.objects.create(
        name='Create a Payroll integration',
        description='Custom Description',
        due_date=datetime.today(),
        metadata=dict(
            referenceId=ACTION_ITEM_FOR_PAYROLL_INTEGRATION,
            organizationId=str(graphql_organization.id),
        ),
    )

    response = on_create_payroll_connection_account_handler(
        {
            'action_item_ref_id': ACTION_ITEM_FOR_PAYROLL_INTEGRATION,
            'organization_id': str(graphql_organization.id),
            'connection_account_id': 1,
        }
    )
    assert not response

    s_002 = ActionItem.objects.get(
        metadata__referenceId=ACTION_ITEM_FOR_PAYROLL_INTEGRATION,
        metadata__organizationId=str(graphql_organization.id),
    )

    assert s_002.status == str(ActionItemStatus.COMPLETED)
    assert s_002.completion_date

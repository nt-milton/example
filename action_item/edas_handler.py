import logging

from action_item.models import ActionItem, ActionItemStatus
from integration.constants import ON_CREATE_PAYROLL_CONNECTION_ACCOUNT

logger = logging.getLogger(__name__)


def on_create_payroll_connection_account_handler(message: dict):
    action_item_ref_id = message.get('action_item_ref_id')
    organization_id = message.get('organization_id')
    connection_account_id = message.get('connection_account_id')

    if not action_item_ref_id or not organization_id:
        logger.warning(
            f'{ON_CREATE_PAYROLL_CONNECTION_ACCOUNT} event payload: {message} is bad '
            'formatted'
        )
        return

    action_item = ActionItem.objects.filter(
        metadata__organizationId=organization_id,
        metadata__referenceId=action_item_ref_id,
    ).first()

    if action_item and action_item.status != str(ActionItemStatus.COMPLETED):
        action_item.complete()
        logger.info(
            'Action Item completed after creating payroll integration. '
            f'action_item: {action_item_ref_id}, organization_id: {organization_id} '
            f'connection_account_id: {connection_account_id}'
        )
    else:
        logger.info(
            'No side effect after connection account created. Action item does '
            'not exist or it is already completed.'
        )

import logging

from action_item.constants import (
    ACTION_ITEM_COMPLETED_EVENT,
    ACTION_ITEM_EDAS_HEALTH_CHECK,
)
from action_item.edas_handler import on_create_payroll_connection_account_handler
from integration.constants import ON_CREATE_PAYROLL_CONNECTION_ACCOUNT
from laika.edas.decorators import Edas
from laika.edas.edas import EdaRegistry
from policy.constants import PUBLISHED_POLICY_EVENT

logger = logging.getLogger(__name__)

EdaRegistry.register_events(
    app=__package__, events=[ACTION_ITEM_COMPLETED_EVENT, ACTION_ITEM_EDAS_HEALTH_CHECK]
)


@Edas.on_event(subscribed_to=ACTION_ITEM_COMPLETED_EVENT)
def process_action_item_completed(message):
    pass


@Edas.on_event(subscribed_to=PUBLISHED_POLICY_EVENT)
def process_policy_published(message):
    pass


@Edas.on_event(subscribed_to=ACTION_ITEM_EDAS_HEALTH_CHECK)
def process_action_item_edas_health_check(message):
    request_id = message['request_id']
    logger.info(f'Message with request_id {request_id} has been successfully received')


@Edas.on_event(subscribed_to=ON_CREATE_PAYROLL_CONNECTION_ACCOUNT)
def on_create_connection_account(message: dict):
    logger.info(f'message {ON_CREATE_PAYROLL_CONNECTION_ACCOUNT} received')
    on_create_payroll_connection_account_handler(message)

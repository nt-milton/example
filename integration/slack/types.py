from typing import Optional

from alert.models import Alert
from integration.models import Integration
from user.models import User as ModelUser

SLACK_ALERT_TYPES = {
    'MENTION': 'MENTION',
    'CONTROL_MENTION': 'MENTION',
    'REPLY': 'REPLY',
    'CONTROL_REPLY': 'REPLY',
    'NEW_ASSIGNMENT': 'NEW_ASSIGNMENT',
    'AUDIT_REQUESTED': 'AUDIT_REQUESTED',
    'AUDIT_INITIATED': 'AUDIT_INITIATED',
    'DRAFT_REPORT_AVAILABLE': 'DRAFT_REPORT_AVAILABLE',
    'AUDIT_COMPLETE': 'AUDIT_COMPLETE',
    'VENDOR_DISCOVERY': 'VENDOR_DISCOVERY',
    'PEOPLE_DISCOVERY': 'PEOPLE_DISCOVERY',
}


class SlackAlert(object):
    def __init__(
        self,
        alert_type,
        receiver,
        alert=None,
        sender=None,
        audit=None,
        quantity: int = 0,
        integration: Optional[Integration] = None,
    ) -> None:
        self.alert_type: str = alert_type
        self.receiver: ModelUser = receiver
        self.alert: Optional[Alert] = alert
        self.sender: Optional[ModelUser] = sender
        self.audit: Optional[str] = audit
        self.quantity: int = quantity
        self.integration: Optional[str] = integration

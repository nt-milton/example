import logging

from alert.constants import PERSONAL_ALERTS
from alert.models import Alert
from laika.utils.websocket import send_ws_message_to_group


def create_alert(
    room_id,
    receiver,
    alert_type,
    alert_related_object=None,
    alert_related_model=None,
    sender=None,
    sender_name='',
    task_related=None,
    audit_status=None,
):
    alert = Alert(
        receiver=receiver,
        sender=sender,
        type=alert_type,
        sender_name=sender_name,
    )

    alert.save(task_related=task_related, audit_status=audit_status)
    if alert_related_model is not None:
        alert_related_model.objects.create(alert=alert, **alert_related_object)
    send_ws_message_to_group(
        room_id=room_id, sender=sender, receiver=receiver.email, logger=logger
    )
    # importing here because it gives circular
    # dependency error ig imported from global
    from integration.slack.implementation import send_alert_to_slack
    from integration.slack.types import SlackAlert

    if alert_type in PERSONAL_ALERTS:
        slack_alert = SlackAlert(
            alert_type=alert_type, sender=sender, receiver=receiver, alert=alert
        )
        send_alert_to_slack(slack_alert)

    return alert


logger = logging.getLogger('create_alert')

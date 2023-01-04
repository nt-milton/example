from comment.models import CommentAlert, Mention, ReplyAlert

from .constants import ALERT_ACTIONS, ALERT_TYPES
from .utils import build_common_response_payload


def control_reply_based_alert(reply_alerts_qs):
    reply_alert = reply_alerts_qs.first()
    mention = Mention.objects.filter(reply=reply_alert.reply).first()
    control = mention.reply.parent.control.first()
    message_content = mention.reply.content
    message_owner = mention.reply.owner_name

    return {
        'message_owner': message_owner,
        'content': message_content,
        'entity_name': control.name,
    }


def control_comment_based_alert(comment_alerts_qs):
    comment_alert = comment_alerts_qs.first()
    mention = Mention.objects.filter(comment=comment_alert.comment).first()
    control = mention.comment.control.first()
    message_content = mention.comment.content
    message_owner = mention.comment.owner_name

    return {
        'message_owner': message_owner,
        'content': message_content,
        'entity_name': control.name,
    }


def build_control_reply(alert):
    reply_alert = ReplyAlert.objects.get(alert=alert)

    control = reply_alert.reply.parent.control.first()
    message_content = reply_alert.reply.content
    message_owner = reply_alert.reply.owner_name

    return {
        'message_owner': message_owner,
        'content': message_content,
        'entity_name': control.name,
    }


def build_control_mention(alert):
    reply_alerts_qs = ReplyAlert.objects.filter(alert=alert)
    if reply_alerts_qs.exists():
        return control_reply_based_alert(reply_alerts_qs)

    comment_alerts_qs = CommentAlert.objects.filter(alert=alert)
    if comment_alerts_qs.exists():
        return control_comment_based_alert(comment_alerts_qs)

    raise ValueError('Reply or Comment missing')


def get_control_alerts_template_context(alerts, logger):
    template_contexts = []
    page_section = 'Control'

    for alert in alerts:
        try:
            alert_action = f'{ALERT_ACTIONS[alert.type].strip()}'

            common_response_payload = build_common_response_payload(
                alert=alert, alert_action=alert_action, page_section=page_section
            )

            if alert.type == ALERT_TYPES['CONTROL_REPLY']:
                control_reply = build_control_reply(alert=alert)

            elif alert.type == ALERT_TYPES['CONTROL_MENTION']:
                control_reply = build_control_mention(alert=alert)

            template_contexts.append({**common_response_payload, **control_reply})

        except Exception:
            logger.error(
                'Unable to get control from ReplyAlert model or '
                'CommentAlert model'
                f' alert sender: {alert.sender_name}'
                f' alert receiver: {alert.receiver}'
                f' alert type: {alert.type}'
            )

    return template_contexts

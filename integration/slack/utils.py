import logging
import re
from typing import Dict, List, Optional

from alert.constants import ALERT_TYPES
from alert.tasks import get_task_and_content_by_alert_type
from alert.types import get_alert_url
from comment.models import CommentAlert, Mention, ReplyAlert
from integration.slack.types import SlackAlert
from laika.settings import DJANGO_SETTINGS
from laika.utils.regex import MENTIONED_EMAILS
from user.models import User

SENDER_PLACEHOLDER = '[Sender]'
RECEIVER_PLACEHOLDER = '[Receiver]'
AUDIT_PLACEHOLDER = '[Audit]'
QUANTITY_PLACEHOLDER = '[Quantity]'
COMMENT_PLACEHOLDER = '[Comment]'
URL_PLACEHOLDER = '[URL]'
SUBTASK_PLACEHOLDER = '[SubtaskGroup]'
TASK_PLACEHOLDER = '[Task]'
SLACK_EMOJIS = {
    'COMMENT': ':speech_balloon:',
    'TASK_COMPLETE': ':ballot_box_with_check:',
    'AUDIT': ':sleuth_or_spy:',
    'DISCOVERY': ':mag:',
}
LAIKA_WEB_URL = DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')

logger_name = __name__
logger = logging.getLogger(logger_name)


def get_blocks_slack_template(title: str, body: str) -> List:
    blocks = [
        {
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': f'*{title}*',
            },
        },
        {'type': 'section', 'text': {'type': 'mrkdwn', 'text': body}},
    ]
    return blocks


def get_alert_task_url(
    url: str, comment_id: Optional[str] = None, comment_state: Optional[str] = None
) -> str:
    alert_url = f'{LAIKA_WEB_URL}/playbooks/{url}?commentsOpen=true&activeTab=subtasks'

    if comment_id and comment_state:
        alert_url = f'{alert_url}&commentId={comment_id}&commentState={comment_state}'

    return alert_url


def get_discovery_data(alert: SlackAlert):
    url = LAIKA_WEB_URL
    if alert.alert_type == ALERT_TYPES['VENDOR_DISCOVERY']:
        url = f'{url}/vendors?discover=1'
        keyword = 'vendors' if alert.quantity > 1 else 'vendor'
        message = (
            '[Quantity] new '
            f'*<[URL]|{keyword} discovered>* via your '
            f'*{alert.integration}* integration'
        )
    else:
        url = f'{url}/people?discover=1'
        keyword = 'people' if alert.quantity > 1 else 'person'
        message = (
            '[Quantity] new '
            f'<[URL]|{keyword} discovered>. '
            '\n\nPlease review and update your people table.'
        )
    return url, message


def get_sender_name(alert: SlackAlert) -> str:
    return alert.sender.get_full_name() if alert.sender else ''


def replace_mentioned_emails_with_names(comment_message: str) -> str:
    mentions = re.findall(MENTIONED_EMAILS, comment_message)
    for mention in mentions:
        try:
            user_mentioned = User.objects.get(email=mention)
            comment_message = comment_message.replace(
                f'@({mention})', f'*`@{user_mentioned.get_full_name()}`*'
            )
        except User.DoesNotExist:
            logger.warning(f'User mentioned with the email {mention} does not exist')
            continue
    return comment_message


def get_comment_message(alert: SlackAlert, message: str) -> str:
    alert_info_related = get_task_and_content_by_alert_type(alert=alert.alert)
    comment_message = alert_info_related.get('message_content')
    comment = alert_info_related.get('comment')
    comment_id = comment.id if comment else None
    comment_state = comment.state if comment else None
    alert_url = get_alert_url(alert.alert)
    comment_url = get_alert_task_url(alert_url, comment_id, comment_state)
    comment_message = replace_mentioned_emails_with_names(comment_message)
    task = alert_info_related.get('task')
    if task:
        message = f'{message} \n\nIn the *`{task}`* task'
    body_message = (
        message.replace(SENDER_PLACEHOLDER, get_sender_name(alert))
        .replace(RECEIVER_PLACEHOLDER, alert.receiver.get_full_name())
        .replace(COMMENT_PLACEHOLDER, comment_message)
        .replace(URL_PLACEHOLDER, comment_url)
    )
    return body_message


def get_control_comment_message(alert: SlackAlert, message: str) -> str:
    comment_info_related = get_control_comment_content(alert)
    is_mention_in_reply = comment_info_related.get('is_mention_in_reply', False)
    if is_mention_in_reply:
        message = (
            '*[Sender]* mentioned *[Receiver]* in a *<[URL]|reply>*\n\n> [Comment]'
        )
    comment_message = comment_info_related.get('message_content', '')
    alert_url = f'{LAIKA_WEB_URL}/{get_alert_url(alert.alert)}'
    comment_message = replace_mentioned_emails_with_names(comment_message)
    control = comment_info_related.get('control')
    if control:
        message = f'{message} \n\nIn the *`{control.name}`* control'
    body_message = (
        message.replace(SENDER_PLACEHOLDER, get_sender_name(alert))
        .replace(RECEIVER_PLACEHOLDER, alert.receiver.get_full_name())
        .replace(COMMENT_PLACEHOLDER, comment_message)
        .replace(URL_PLACEHOLDER, alert_url)
    )
    return body_message


def get_task_message(alert: SlackAlert, message: str) -> str:
    alert_info_related = get_task_and_content_by_alert_type(alert=alert.alert)
    task_name = alert_info_related.get('task').name
    subtask_group = alert_info_related.get('subtask_group')
    alert_url = get_alert_url(alert.alert)
    task_url = get_alert_task_url(alert_url)
    body_message = (
        message.replace(RECEIVER_PLACEHOLDER, alert.receiver.get_full_name())
        .replace(TASK_PLACEHOLDER, task_name)
        .replace(SUBTASK_PLACEHOLDER, subtask_group)
        .replace(URL_PLACEHOLDER, task_url)
    )
    return body_message


def get_mention_message(alert: SlackAlert) -> List:
    message = '*[Sender]* mentioned *[Receiver]* in a *<[URL]|comment>:*\n\n> [Comment]'
    body_message = get_comment_message(alert, message)
    title = f'{SLACK_EMOJIS["COMMENT"]} New Mention'
    return get_blocks_slack_template(title, body_message)


def get_control_mention_message(alert: SlackAlert) -> List:
    message = '*[Sender]* mentioned *[Receiver]* in a *<[URL]|comment>:*\n\n> [Comment]'
    body_message = get_control_comment_message(alert, message)
    title = f'{SLACK_EMOJIS["COMMENT"]} New Mention'
    return get_blocks_slack_template(title, body_message)


def get_control_reply_message(alert: SlackAlert) -> List:
    message = (
        '*[Sender]* replied to a *<[URL]|comment>* from *[Receiver]* \n\n> [Comment]'
    )
    body_message = get_control_comment_message(alert, message)
    title = f'{SLACK_EMOJIS["COMMENT"]} New Reply'
    return get_blocks_slack_template(title, body_message)


def get_reply_message(alert: SlackAlert) -> List:
    message = (
        '*[Sender]* replied to a *<[URL]|comment>* from *[Receiver]*\n\n> [Comment]'
    )
    body_message = get_comment_message(alert, message)
    title = f'{SLACK_EMOJIS["COMMENT"]} New Reply'
    return get_blocks_slack_template(title, body_message)


def get_new_assignment_message(alert: SlackAlert) -> List:
    message = (
        '*[Receiver]* has been assigned a '
        '*[SubtaskGroup]* subtask due in:'
        '\n\n> *<[URL]|[Task]>*'
    )
    body_message = get_task_message(alert, message)
    title = f'{SLACK_EMOJIS["TASK_COMPLETE"]} New Assignment'
    return get_blocks_slack_template(title, body_message)


def get_audit_message(alert: SlackAlert) -> List:
    message = SLACK_ALERTS_TEMPLATE[alert.alert_type].get('message_template', '')
    body_message = message.replace(AUDIT_PLACEHOLDER, alert.audit)
    alert_title = alert.alert_type.replace('_', ' ')
    title = f'{SLACK_EMOJIS["AUDIT"]} {alert_title}'
    return get_blocks_slack_template(title, body_message)


def get_discovery_message(alert: SlackAlert) -> List:
    discovery_url, message = get_discovery_data(alert)
    body_message = message.replace(QUANTITY_PLACEHOLDER, str(alert.quantity)).replace(
        URL_PLACEHOLDER, discovery_url
    )
    title = f'{SLACK_EMOJIS["DISCOVERY"]} Discovery'
    return get_blocks_slack_template(title, body_message)


def get_control_comment_content(alert: SlackAlert):
    reply_alert_qs = ReplyAlert.objects.filter(alert=alert.alert)
    comment_alert_qs = CommentAlert.objects.filter(alert=alert.alert)
    mention_info_related = {}
    if reply_alert_qs.exists():
        reply_alert = reply_alert_qs.first()
        mention = Mention.objects.filter(reply=reply_alert.reply).first()
        if mention:
            mention_info_related = mention.get_mention_control_related()
            mention_info_related['is_mention_in_reply'] = True
        else:
            reply_controls = reply_alert.reply.parent.control_comments
            control_by_reply = reply_controls.first().control
            mention_info_related = {
                'control': control_by_reply,
                'message_content': reply_alert.reply.content,
                'message_owner': reply_alert.reply.owner_name,
            }
    elif comment_alert_qs.exists():
        comment_alert = comment_alert_qs.first()
        mention = Mention.objects.filter(comment=comment_alert.comment).first()
        mention_info_related = mention.get_mention_control_related()
    return mention_info_related


SLACK_ALERTS_TEMPLATE: Dict = {
    ALERT_TYPES['MENTION']: {'message_parser': get_mention_message},
    ALERT_TYPES['CONTROL_MENTION']: {'message_parser': get_control_mention_message},
    ALERT_TYPES['REPLY']: {'message_parser': get_reply_message},
    ALERT_TYPES['CONTROL_REPLY']: {'message_parser': get_control_reply_message},
    ALERT_TYPES['NEW_ASSIGNMENT']: {'message_parser': get_new_assignment_message},
    ALERT_TYPES['AUDIT_REQUESTED']: {
        'message_template': 'Your organization requested a [Audit] audit',
        'message_parser': get_audit_message,
    },
    ALERT_TYPES['AUDIT_INITIATED']: {
        'message_template': 'Your [Audit] audit has been initiated',
        'message_parser': get_audit_message,
    },
    ALERT_TYPES['DRAFT_REPORT_AVAILABLE']: {
        'message_template': 'Your Draft Report is available for review',
        'message_parser': get_audit_message,
    },
    ALERT_TYPES['AUDIT_COMPLETE']: {
        'message_template': 'Your [Audit] is now complete',
        'message_parser': get_audit_message,
    },
    ALERT_TYPES['VENDOR_DISCOVERY']: {
        'message_template': '[Quantity] new vendor(s) discovered',
        'message_parser': get_discovery_message,
    },
    ALERT_TYPES['PEOPLE_DISCOVERY']: {
        'message_template': '[Quantity] new people discovered',
        'message_parser': get_discovery_message,
    },
}

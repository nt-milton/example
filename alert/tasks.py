import logging
from datetime import datetime, timedelta

import pytz

from audit.models import AuditAlert, AuditStatus
from comment.models import CommentAlert, Mention, ReplyAlert
from laika.aws.ses import send_email
from laika.celery import app as celery_app
from laika.settings import DJANGO_SETTINGS, NO_REPLY_EMAIL
from organization.models import Organization
from program.models import SubtaskAlert
from user.constants import ALERT_PREFERENCES

from .constants import ALERT_ACTIONS, ALERT_TYPES
from .models import Alert
from .utils import (
    AUDIT_ALERT_FILTER,
    COMMENT_ALERT_FILTER,
    CONTROL_ALERT_FILTER,
    POLICY_ALERT_FILTER,
    calculate_surpass_alerts,
    send_audit_alert_email,
    trim_alerts,
)
from .utils_control import get_control_alerts_template_context
from .utils_policy import get_policy_alerts_template_context

logger = logging.getLogger('digest_email_task')


def get_mention_message(alert):
    task = None
    message_content = None
    message_owner = None
    comment = None

    reply_alerts_qs = ReplyAlert.objects.filter(alert=alert)
    comment_alerts_qs = CommentAlert.objects.filter(alert=alert)

    if reply_alerts_qs.exists():
        reply_alert = reply_alerts_qs.first()
        mention = Mention.objects.filter(reply=reply_alert.reply).first()
        comment = reply_alert.reply.parent
        task = mention.reply.parent.task.first().task
        message_content = mention.reply.content
        message_owner = mention.reply.owner_name
    elif comment_alerts_qs.exists():
        comment_alert = comment_alerts_qs.first()
        mention = Mention.objects.filter(comment=comment_alert.comment).first()
        comment = comment_alert.comment

        task = mention.comment.task.first().task
        message_content = mention.comment.content
        message_owner = mention.comment.owner_name

    return {
        'task': task,
        'message_content': message_content,
        'message_owner': message_owner,
        'comment': comment,
    }


def get_task_and_content_by_alert_type(alert):
    task = None
    message_content = None
    subtask = None
    message_owner = None
    comment = None

    if alert.type == ALERT_TYPES['MENTION']:
        mention = get_mention_message(alert)

        task = mention.get('task')
        message_content = mention.get('message_content')
        message_owner = mention.get('message_owner')
        comment = mention.get('comment')
    elif alert.type == ALERT_TYPES['RESOLVE']:
        comment_alert = CommentAlert.objects.get(alert=alert)

        task = comment_alert.comment.task.first().task
        message_content = comment_alert.comment.content
        message_owner = comment_alert.comment.owner_name
        comment = comment_alert.comment
    elif alert.type == ALERT_TYPES['REPLY']:
        try:
            reply_alert = ReplyAlert.objects.get(alert=alert)

            task = reply_alert.reply.parent.task.first().task
            comment = reply_alert.reply.parent
            message_content = reply_alert.reply.content
            message_owner = reply_alert.reply.owner_name
        except Exception:
            logger.error(
                'Unable to get task from ReplyAlert model'
                f' alert sender: {alert.sender_name}'
                f' alert receiver: {alert.receiver}'
                f' alert type: {alert.type}'
            )
    elif (
        alert.type == ALERT_TYPES['NEW_ASSIGNMENT']
        or alert.type == ALERT_TYPES['ASSIGNMENT_COMPLETED']
    ):
        subtask_alert = SubtaskAlert.objects.get(alert=alert)
        subtask = subtask_alert.subtask
        task = subtask_alert.subtask.task
    return {
        'task': task,
        'message_content': message_content,
        'subtask_group': subtask.group if subtask else None,
        'message_owner': message_owner,
        'comment': comment,
    }


def get_all_users_by_alert_preference(alert_preference):
    orgs = Organization.objects.all()
    users = []
    for org in orgs:
        users_by_org = org.users.filter(
            user_preferences__profile__alerts=alert_preference
        )
        users.extend(users_by_org)
    return users


def build_email_context(alerts_template_context, additional_alerts):
    hostname = DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')
    template_context = {
        'alerts': alerts_template_context,
        'call_to_action_url': f'{hostname}/dashboard/?alertsOpen=true',
    }
    if additional_alerts > 0:
        template_context['additional_alerts'] = additional_alerts

    return template_context


def get_alerts_template_context(alerts):
    alerts_template_context = []

    for alert in alerts:
        alert_info_related = get_task_and_content_by_alert_type(alert=alert)

        task = alert_info_related.get('task')
        message_content = alert_info_related.get('message_content')
        message_owner = alert_info_related.get('message_owner')

        if task is None:
            logger.error(f'No task found for alert: {alert.id}')
        else:
            alerts_template_context.append(
                {
                    'sender_name': alert.sender_name,
                    'message_owner': message_owner,
                    'alert_action': f'{ALERT_ACTIONS[alert.type].strip()} comment',
                    'created_at': alert.created_at,
                    'content': message_content,
                    'task_name': task.name,
                }
            )

    return alerts_template_context


def get_alerts_by_group(user, date_from):
    alerts = Alert.objects.filter(
        COMMENT_ALERT_FILTER,
        receiver=user,
        created_at__gte=date_from,
    ).order_by('-created_at')

    audit_alerts = Alert.objects.filter(
        AUDIT_ALERT_FILTER,
        receiver=user,
        created_at__gte=date_from,
    ).order_by('-created_at')

    control_alerts = Alert.objects.filter(
        CONTROL_ALERT_FILTER,
        receiver=user,
        created_at__gte=date_from,
    ).order_by('-created_at')

    policy_alerts = Alert.objects.filter(
        POLICY_ALERT_FILTER,
        receiver=user,
        created_at__gte=date_from,
    ).order_by('-created_at')

    return [alerts, audit_alerts, control_alerts, policy_alerts]


@celery_app.task(name='Digest alert emails')
def send_digest_alert_email(*args):
    users = get_all_users_by_alert_preference(
        alert_preference=ALERT_PREFERENCES['DAILY']
    )

    emails_sent = 0
    if len(users) == 0:
        logger.info('No users found with Daily alert preference')
        return {'success': True, 'emails_sent': emails_sent}

    date_from = datetime.now(pytz.utc) - timedelta(days=1)
    missed_users = []
    logger.info(f'Sending digest alert email to {len(users)} users')
    for user in users:
        alerts, audit_alerts, control_alerts, policy_alerts = get_alerts_by_group(
            user=user, date_from=date_from
        )

        if (
            not alerts.exists()
            and not audit_alerts.exists()
            and not control_alerts.exists()
            and not policy_alerts.exists()
        ):
            missed_users.append(user.email)
            continue

        alerts_context = get_alerts_template_context(alerts=alerts)

        control_alerts_context = get_control_alerts_template_context(
            alerts=control_alerts, logger=logger
        )

        policy_alerts_context = get_policy_alerts_template_context(
            alerts=policy_alerts, logger=logger
        )

        alerts_template_context = [
            *alerts_context,
            *control_alerts_context,
            *policy_alerts_context,
        ]

        template_context = build_email_context(
            alerts_template_context=trim_alerts(alerts_template_context),
            additional_alerts=calculate_surpass_alerts(alerts, control_alerts),
        )

        if len(alerts_template_context) > 0:
            send_email(
                subject='New Alerts in Laika',
                from_email=NO_REPLY_EMAIL,
                to=[user.email],
                template='alert_email.html',
                template_context=template_context,
            )
            emails_sent += 1

        hostname = DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')

        for alert in audit_alerts:
            audit_alert = AuditAlert.objects.get(alert=alert)
            audit = audit_alert.audit
            audit_status = AuditStatus.objects.get(audit=audit)

            send_audit_alert_email(
                alert=alert,
                audit_status=audit_status,
                hostname=hostname,
            )
            emails_sent += 1

    logger.info(f'Email was sent successfully to {emails_sent} users')
    logger.info(f'Missed users: {missed_users}')

    return {'success': True, 'emails_sent': emails_sent, 'missed_users': missed_users}

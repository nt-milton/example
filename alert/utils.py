import logging
from datetime import datetime

from django.db.models import Q

from laika.aws.ses import send_email
from laika.celery import app as celery_app
from laika.settings import NO_REPLY_EMAIL
from user.constants import ALERT_PREFERENCES, AUDITOR_ROLES

from .constants import (
    ALERT_ACTIONS,
    ALERT_EMAIL_SUBJECTS,
    ALERT_EMAIL_SUBJECTS_AUDITOR,
    ALERT_EMAIL_SUBJECTS_CONTROL,
    ALERT_EMAIL_SUBJECTS_EVIDENCE,
    ALERT_EMAIL_SUBJECTS_POLICY,
    ALERT_EMAIL_TEMPLATES,
    ALERT_TYPE_USER,
    ALERT_TYPES,
    ALERT_TYPES_ACCESS_REVIEW,
    ALERT_TYPES_AUDIT_USER,
    ALERT_TYPES_AUDITOR,
    ALERT_TYPES_BACKGROUND_CHECK,
    ALERT_TYPES_LAIKA_OBJECTS,
    ALERTS_MAX_NUMBER,
    AUDIT_ALERT_EMAIL_CONTENT,
    AUDIT_ALERT_EMAIL_CTA,
    AUDITOR_ALERT_EMAIL_CONTENT,
)

logger = logging.getLogger('alert_utils')

COMPANY_NAME_PLACEHOLDER = '[CompanyName]'
AUDIT_TYPE_PLACEHOLDER = '[AuditType]'
USER_TYPE_PLACEHOLDER = '[User]'

COMMENT_ALERT_FILTER = (
    Q(type=ALERT_TYPES['MENTION'])
    | Q(type=ALERT_TYPES['REPLY'])
    | Q(type=ALERT_TYPES['RESOLVE'])
)

AUDIT_ALERT_FILTER = (
    Q(type=ALERT_TYPES['AUDIT_INITIATED'])
    | Q(type=ALERT_TYPES['DRAFT_REPORT_AVAILABLE'])
    | Q(type=ALERT_TYPES['AUDIT_COMPLETE'])
)

CONTROL_ALERT_FILTER = Q(type=ALERT_TYPES['CONTROL_REPLY']) | Q(
    type=ALERT_TYPES['CONTROL_MENTION']
)

POLICY_ALERT_FILTER = Q(type=ALERT_TYPES['POLICY_REPLY']) | Q(
    type=ALERT_TYPES['POLICY_MENTION']
)


def build_common_response_payload(alert, alert_action, page_section):
    return {
        'sender_name': alert.sender_name,
        'alert_action': alert_action,
        'created_at': alert.created_at,
        'page_section': page_section,
    }


def is_playbook_alert(alert_type):
    alert_types = [
        ALERT_TYPES['MENTION'],
        ALERT_TYPES['RESOLVE'],
        ALERT_TYPES['REPLY'],
        ALERT_TYPES['NEW_ASSIGNMENT'],
        ALERT_TYPES['ASSIGNMENT_COMPLETED'],
    ]
    return alert_type in alert_types


def is_evidence_comment_alert(alert_type):
    alert_types = [ALERT_TYPES['EVIDENCE_MENTION'], ALERT_TYPES['EVIDENCE_REPLY']]
    return alert_type in alert_types


def is_requirement_comment_alert(alert_type):
    alert_types = [ALERT_TYPES['REQUIREMENT_MENTION'], ALERT_TYPES['REQUIREMENT_REPLY']]
    return alert_type in alert_types


def is_control_comment_alert(alert_type):
    alert_types = [ALERT_TYPES['CONTROL_MENTION'], ALERT_TYPES['CONTROL_REPLY']]
    return alert_type in alert_types


def is_policy_comment_alert(alert_type):
    alert_types = [ALERT_TYPES['POLICY_MENTION'], ALERT_TYPES['POLICY_REPLY']]
    return alert_type in alert_types


def is_control_action_item_assignment_alert(alert_type):
    return alert_type == ALERT_TYPES['CONTROL_ACTION_ITEM_ASSIGNMENT']


def is_question_assignment_alert(alert_type):
    return alert_type == ALERT_TYPES['QUESTION_ASSIGNMENT']


def is_library_entry_suggestions_alert(alert_type):
    return alert_type == ALERT_TYPES['LIBRARY_ENTRY_SUGGESTIONS']


def is_control_action_item_period_alert(alert_type):
    return (
        alert_type == ALERT_TYPES['CONTROL_FUTURE_DUE_ACTION_ITEM']
        or alert_type == ALERT_TYPES['CONTROL_PAST_DUE_ACTION_ITEM']
    )


def is_audit_alert(alert_type):
    alert_types = [
        ALERT_TYPES['AUDIT_INITIATED'],
        ALERT_TYPES['AUDIT_COMPLETE'],
        ALERT_TYPES['FIELDWORK_INITIATED'],
        ALERT_TYPES['DRAFT_REPORT_AVAILABLE'],
        ALERT_TYPES['ORG_SUGGESTED_DRAFT_EDITS'],
        ALERT_TYPES['ORG_APPROVED_DRAFT_REPORT'],
        ALERT_TYPES['AUDITOR_PUBLISHED_DRAFT_REPORT'],
    ]
    return alert_type in alert_types


def is_draft_report_comment_alert(alert_type):
    alert_types = [ALERT_TYPES['AUDITEE_DRAFT_REPORT_MENTION']]

    return alert_type in alert_types


def is_discovery_alert(alert_type):
    discovery_types = [ALERT_TYPES['PEOPLE_DISCOVERY'], ALERT_TYPES['VENDOR_DISCOVERY']]
    return alert_type in discovery_types


def is_training_alert(alert_type):
    return alert_type == ALERT_TYPES['TRAINING_REMINDER']


def is_auditor_alert(alert_type):
    auditor_alerts_types = ALERT_TYPES_AUDITOR.keys()
    return alert_type in auditor_alerts_types


def is_laika_object_alert(alert_type):
    return alert_type in ALERT_TYPES_LAIKA_OBJECTS.keys()


def is_user_alert(alert_type):
    return alert_type in ALERT_TYPE_USER.keys()


def is_background_check_alert(alert_type):
    return alert_type in ALERT_TYPES_BACKGROUND_CHECK.keys()


def is_access_review_alert(alert_type):
    return alert_type in ALERT_TYPES_ACCESS_REVIEW.keys()


@celery_app.task(name='Send alert emails')
def send_alert_email(email_info, template):
    to = email_info['to']
    subject = email_info['subject']
    template_context = email_info['template_context']

    if 'alerts' in template_context:
        for alert in template_context['alerts']:
            alert['created_at'] = datetime.fromisoformat(alert['created_at'])

    send_email(
        subject=subject,
        from_email=NO_REPLY_EMAIL,
        to=[to],
        template=template,
        template_context=template_context,
    )
    return {'success': True}


def get_alert_email_subject(alert_type, sender_name, task_name):
    return (
        ALERT_EMAIL_SUBJECTS[alert_type]
        .replace(USER_TYPE_PLACEHOLDER, sender_name)
        .replace('[TaskName]', task_name)
    )


def get_audit_alert_email_subject(alert_type, audit_type):
    return ALERT_EMAIL_SUBJECTS[alert_type].replace(AUDIT_TYPE_PLACEHOLDER, audit_type)


def get_audit_alert_email_content(alert_type, company_name):
    return AUDIT_ALERT_EMAIL_CONTENT[alert_type].replace(
        COMPANY_NAME_PLACEHOLDER, company_name
    )


def get_auditor_alert_email_subject(alert_type, company_name, audit_type):
    return (
        ALERT_EMAIL_SUBJECTS_AUDITOR[alert_type]
        .replace(COMPANY_NAME_PLACEHOLDER, company_name)
        .replace(AUDIT_TYPE_PLACEHOLDER, audit_type)
    )


def get_evidence_alert_email_subject(alert_type, sender_name, evidence):
    return (
        ALERT_EMAIL_SUBJECTS_EVIDENCE[alert_type]
        .replace(USER_TYPE_PLACEHOLDER, sender_name)
        .replace('[EvidenceName]', evidence.name)
        .replace('[AuditName]', evidence.audit.name)
    )


def get_control_alert_email_subject(alert_type, sender_name, control_name):
    return (
        ALERT_EMAIL_SUBJECTS_CONTROL[alert_type]
        .replace(USER_TYPE_PLACEHOLDER, sender_name)
        .replace('[ControlName]', control_name)
    )


def get_policy_alert_email_subject(alert_type, sender_name, policy_name):
    return (
        ALERT_EMAIL_SUBJECTS_POLICY[alert_type]
        .replace(USER_TYPE_PLACEHOLDER, sender_name)
        .replace('[PolicyName]', policy_name)
    )


def get_auditor_alert_email_content(alert_type, company_name):
    return AUDITOR_ALERT_EMAIL_CONTENT[alert_type].replace(
        COMPANY_NAME_PLACEHOLDER, company_name
    )


def should_send_alert_email(alert_preference):
    return alert_preference == ALERT_PREFERENCES['IMMEDIATELY']


def get_audit_alert_template(alert):
    auditor_alert_types = ALERT_TYPES_AUDITOR.values()
    audit_user_alert_types = ALERT_TYPES_AUDIT_USER.values()

    if alert.type in auditor_alert_types:
        return ALERT_EMAIL_TEMPLATES['AUDITOR']
    elif alert.type in audit_user_alert_types:
        return ALERT_EMAIL_TEMPLATES['AUDITS']


def send_audit_alert_email(alert, audit_status, hostname):
    subject = get_audit_alert_email_subject(
        alert_type=alert.type, audit_type=audit_status.audit.audit_type
    )

    email_info = {
        'to': alert.receiver.email,
        'subject': subject,
        'template_context': {
            'status_title': subject,
            'status_description': get_audit_alert_email_content(
                alert_type=alert.type, company_name=audit_status.audit.organization.name
            ),
            'status_cta': AUDIT_ALERT_EMAIL_CTA[alert.type],
            'call_to_action_url': f'{hostname}/audits/{audit_status.audit.id}/',
            'audit_type': audit_status.audit.audit_type,
            'audit_completed': audit_status.completed,
        },
    }

    template = get_audit_alert_template(alert)

    send_alert_email.delay(email_info, template)


def send_auditor_alert_email(alert, audit_status, hostname):
    subject = get_auditor_alert_email_subject(
        alert_type=alert.type,
        audit_type=audit_status.audit.audit_type,
        company_name=audit_status.audit.organization.name,
    )

    email_info = {
        'to': alert.receiver.email,
        'subject': subject,
        'template_context': {
            'status_title': subject,
            'status_description': get_auditor_alert_email_content(
                alert_type=alert.type, company_name=audit_status.audit.organization.name
            ),
            'status_cta': AUDIT_ALERT_EMAIL_CTA[alert.type],
            'call_to_action_url': f'{hostname}/audits/{audit_status.audit.id}/',
            'audit_type': audit_status.audit.audit_type,
            'audit_completed': audit_status.completed,
        },
    }

    template = get_audit_alert_template(alert)

    send_alert_email.delay(email_info, template)


def send_comment_task_alert_email(alert, task_related, hostname):
    task = task_related['task']
    alert_action = f'{ALERT_ACTIONS[alert.type].strip()} comment'
    call_to_action_url = (
        f'{hostname}/playbooks/{task.program.id}/'
        f'{task.id}?activeTab=subtasks&commentsOpen=true'
    )
    page_section = 'Playbook task'
    subject = get_alert_email_subject(
        alert_type=alert.type, sender_name=alert.sender_name, task_name=task.name
    )

    build_comment_alert_email(
        alert,
        task,
        task_related,
        alert_action,
        call_to_action_url,
        page_section,
        subject,
    )


def send_comment_control_alert_email(alert, control_related, hostname):
    control = control_related['control']
    alert_action = f'{ALERT_ACTIONS[alert.type].strip()}'
    call_to_action_url = f'{hostname}/controls/{control.id}'
    page_section = 'Control'
    subject = get_control_alert_email_subject(
        alert_type=alert.type, sender_name=alert.sender_name, control_name=control.name
    )

    build_comment_alert_email(
        alert,
        control,
        control_related,
        alert_action,
        call_to_action_url,
        page_section,
        subject,
    )


def send_comment_policy_alert_email(alert, policy_message_data, hostname):
    policy = policy_message_data['policy']
    alert_action = f'{ALERT_ACTIONS[alert.type].strip()}'
    call_to_action_url = f'{hostname}/policies/{policy.id}'
    page_section = 'Policies'
    subject = get_policy_alert_email_subject(
        alert_type=alert.type, sender_name=alert.sender_name, policy_name=policy.name
    )

    build_comment_alert_email(
        alert=alert,
        entity=policy,
        entity_related=policy_message_data,
        alert_action=alert_action,
        call_to_action_url=call_to_action_url,
        page_section=page_section,
        subject=subject,
    )


def build_comment_alert_email(
    alert,
    entity,
    entity_related,
    alert_action,
    call_to_action_url,
    page_section,
    subject,
):
    email_info = {
        'to': alert.receiver.email,
        'subject': subject,
        'template_context': {
            'alerts': [
                {
                    'sender_name': alert.sender_name,
                    'message_owner': entity_related['message_owner'],
                    'alert_action': alert_action,
                    'created_at': alert.created_at.isoformat(),
                    'content': entity_related['message_content'],
                    'entity_name': entity.name,
                    'page_section': page_section,
                }
            ],
            'call_to_action_url': call_to_action_url,
        },
    }
    send_alert_email.delay(email_info, ALERT_EMAIL_TEMPLATES['COMMENTS'])


def calculate_surpass_alerts(*alerts):
    alerts_sum = sum([alert_group.count() for alert_group in alerts])

    return alerts_sum - ALERTS_MAX_NUMBER


def trim_alerts(alerts):
    return alerts[0:ALERTS_MAX_NUMBER]


def send_evidence_comment_alert_email(
    alert,
    content,
    evidence,
    action,
    hostname,
):
    is_auditor = AUDITOR_ROLES['AUDITOR'] in alert.receiver.role
    email_info = {
        'to': alert.receiver.email,
        'subject': get_evidence_alert_email_subject(
            alert_type=alert.type, sender_name=alert.sender_name, evidence=evidence
        ),
        'template_context': {
            'alerts': [
                {
                    'sender_name': alert.sender_name,
                    'message_owner': alert.sender_name,
                    'alert_action': action,
                    'created_at': alert.created_at.isoformat(),
                    'content': content,
                    'evidence_name': evidence.name,
                    'audit_name': evidence.audit.name,
                }
            ],
            'call_to_action_url': (
                f'{hostname}/audits/{evidence.audit.id}/evidence-detail/{evidence.id}'
            ),
            'is_auditor': is_auditor,
        },
    }
    return send_alert_email.delay(
        email_info, ALERT_EMAIL_TEMPLATES['EVIDENCE_COMMENTS']
    )


def get_evidence_from_alert(alert):
    if alert.type == ALERT_TYPES['EVIDENCE_MENTION'] and alert.comment_alert.first():
        comment_alert = alert.comment_alert.first()
        evidence_comment = comment_alert.comment.evidence_comments.first()
    else:
        reply_alert = alert.reply_alert.first()
        comment = reply_alert.reply.parent
        evidence_comment = comment.evidence_comments.first()
    if not evidence_comment:
        logger.info(f'CommentAlert does not exist. Alert ID: {alert.id}')
    else:
        if not evidence_comment.evidence:
            logger.info(f'Evidence does not exist. Alert ID: {alert.id}')
    return evidence_comment.evidence if evidence_comment else None


def get_control_from_alert(alert):
    if alert.type == ALERT_TYPES['CONTROL_MENTION'] and alert.comment_alert.first():
        comment_alert = alert.comment_alert.first()
        control_comment = comment_alert.comment.control_comments.first()
        control = control_comment.control
    else:
        reply_alert = alert.reply_alert.first()
        comment = reply_alert.reply.parent
        control_comment = comment.control_comments.first()
        control = control_comment.control
    return control


def get_policy_from_alert(alert):
    if alert.type == ALERT_TYPES['POLICY_MENTION'] and alert.comment_alert.first():
        comment_alert = alert.comment_alert.first()
        policy_comment = comment_alert.comment.policy_comments.first()
        policy = policy_comment.policy
    else:
        reply_alert = alert.reply_alert.first()
        comment = reply_alert.reply.parent
        policy_comment = comment.policy_comments.first()
        policy = policy_comment.policy
    return policy


def get_action_item_from_alert(alert):
    action_item_alert = alert.action_items.first()
    return action_item_alert


def get_control_from_action_item(action_item):
    control = action_item.controls.first()
    return control


def get_requirement_from_alert(alert):
    if not is_requirement_comment_alert(alert.type):
        return None
    if alert.type == ALERT_TYPES['REQUIREMENT_MENTION'] and alert.comment_alert.first():
        comment_alert = alert.comment_alert.first()
        requirement_comment = comment_alert.comment.requirement_comments.first()
        return requirement_comment.requirement if requirement_comment else None

    reply_alert = alert.reply_alert.first()
    comment = reply_alert.reply.parent
    requirement_comment = comment.requirement_comments.first()
    return requirement_comment.requirement if requirement_comment else None


def get_audit_from_alert(alert):
    if is_evidence_comment_alert(alert.type):
        evidence = get_evidence_from_alert(alert)
        return evidence.audit

    elif is_requirement_comment_alert(alert.type):
        requirement = get_requirement_from_alert(alert)
        return requirement.audit if requirement else None
    else:
        audit_alert = alert.audit_alert.first()
        return audit_alert.audit


def get_questionnaire_from_alert(alert):
    assigned_alert = alert.questionnaire_alert.first()
    return assigned_alert.questionnaire


def get_library_entry_suggestions_from_alert(alert):
    library_entry_suggestions_alert = alert.library_entry_suggestions_alert.first()
    return library_entry_suggestions_alert

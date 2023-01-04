from alert.models import Alert
from alert.utils import (
    get_action_item_from_alert,
    get_control_from_action_item,
    get_questionnaire_from_alert,
)


def get_url_user_alert(alert: Alert):
    user_alert = alert.user_alert.first()
    if user_alert is None:
        return 'not-found'
    user = user_alert.user
    user_id = user.username if user.is_active and user.username else user.id
    return f'people?userId={user_id}'


def get_url_background_alert(alert: Alert):
    return 'lob/background_check'


def get_url_question_assignment_alert(alert: Alert):
    questionnaire = get_questionnaire_from_alert(alert)
    return f'questionnaires/{questionnaire.id}'


def get_url_control_alert(alert: Alert):
    action_item = get_action_item_from_alert(alert)
    control = get_control_from_action_item(action_item)
    return f'controls/{control.id}'


def get_url_auditee_draft_report_alert(alert: Alert):
    audit = alert.reply_alert.first().reply.parent.draft_report_comments.first().audit
    return f'audits/{audit.id}' if audit else None


ALERT_TYPE_RESOLVE_HELPERS = {
    0: {'resolve_url': get_url_background_alert},
    1: {'resolve_url': get_url_user_alert},
    2: {'resolve_url': get_url_question_assignment_alert},
    3: {'resolve_url': get_url_control_alert},
    4: {'resolve_url': get_url_auditee_draft_report_alert},
}

ALERT_TYPES_INDEX_HELPER = {
    'LO_BACKGROUND_CHECK_ACCOUNT_CREDENTIALED': 0,
    'LO_BACKGROUND_CHECK_TOKEN_DEAUTHORIZED': 0,
    'LO_BACKGROUND_CHECK_SINGLE_MATCH_USER_TO_LO': 1,
    'LO_BACKGROUND_CHECK_MULTIPLE_MATCH_USER_TO_LO': 1,
    'QUESTION_ASSIGNMENT': 2,
    'CONTROL_ACTION_ITEM_ASSIGNMENT': 3,
    'CONTROL_FUTURE_DUE_ACTION_ITEM': 3,
    'CONTROL_PAST_DUE_ACTION_ITEM': 3,
    'AUDITEE_DRAFT_REPORT_MENTION': 4,
}

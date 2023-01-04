ALERT_ACTIONS = {
    'MENTION': ' mentioned you in a  ',
    'REPLY': ' replied to a  ',
    'RESOLVE': ' resolved a ',
    'NEW_ASSIGNMENT': ' are assigned a ',
    'CONTROL_ACTION_ITEM_ASSIGNMENT': ' are assigned ',
    'ASSIGNMENT_COMPLETED': ' completed your ',
    'EVIDENCE_MENTION': ' mentioned you in a comment:',
    'EVIDENCE_REPLY': ' replied to a comment:',
    'CONTROL_PAST_DUE_ACTION_ITEM': ' have an ',
    'CONTROL_FUTURE_DUE_ACTION_ITEM': ' have an ',
    'AUDITEE_DRAFT_REPORT_MENTION': 'mentioned you in a comment: ',
    'QUESTION_ASSIGNMENT': ' assigned you a DDQ ',
    'LIBRARY_ENTRY_SUGGESTIONS': ' available for Library.',
    'ACCESS_REVIEW_START': ' has started. View ',
    'ACCESS_REVIEW_COMPLETE': ' has been completed. ',
}

ALERT_ACTIONS['CONTROL_REPLY'] = ALERT_ACTIONS['EVIDENCE_REPLY']
ALERT_ACTIONS['POLICY_REPLY'] = ALERT_ACTIONS['EVIDENCE_REPLY']
ALERT_ACTIONS['CONTROL_MENTION'] = ALERT_ACTIONS['EVIDENCE_MENTION']
ALERT_ACTIONS['POLICY_MENTION'] = ALERT_ACTIONS['EVIDENCE_MENTION']

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 12


ALERT_TYPES_AUDITOR = {
    'ORG_REQUESTED_AUDIT': 'ORG_REQUESTED_AUDIT',
    'ORG_COMPLETED_DRAFT_REPORT': 'ORG_COMPLETED_DRAFT_REPORT',
    'ORG_COMPLETED_INITIATION': 'ORG_COMPLETED_INITIATION',
}

ALERT_TYPES_AUDIT_USER = {
    'AUDIT_REQUESTED': 'AUDIT_REQUESTED',
    'AUDIT_INITIATED': 'AUDIT_INITIATED',
    'FIELDWORK_INITIATED': 'FIELDWORK_INITIATED',
    'DRAFT_REPORT_AVAILABLE': 'DRAFT_REPORT_AVAILABLE',
    'AUDIT_COMPLETE': 'AUDIT_COMPLETE',
}

ALERT_TYPES_COMMENT = {
    'MENTION': 'MENTION',
    'REPLY': 'REPLY',
    'RESOLVE': 'RESOLVE',
}

ALERT_TYPES_TASK = {
    'NEW_ASSIGNMENT': 'NEW_ASSIGNMENT',
    'ASSIGNMENT_COMPLETED': 'ASSIGNMENT_COMPLETED',
    'AUDIT_REQUESTED': 'AUDIT_REQUESTED',
    'AUDIT_INITIATED': 'AUDIT_INITIATED',
    'DRAFT_REPORT_AVAILABLE': 'DRAFT_REPORT_AVAILABLE',
    'AUDIT_COMPLETE': 'AUDIT_COMPLETE',
    'QUESTION_ASSIGNMENT': 'QUESTION_ASSIGNMENT',
    'LIBRARY_ENTRY_SUGGESTIONS': 'LIBRARY_ENTRY_SUGGESTIONS',
}

ALERT_TYPES_DISCOVERY = {
    'VENDOR_DISCOVERY': 'VENDOR_DISCOVERY',
    'PEOPLE_DISCOVERY': 'PEOPLE_DISCOVERY',
}

ALERT_TYPES_TRAINING = {
    'TRAINING_REMINDER': 'TRAINING_REMINDER',
}

ALERT_TYPES_CX = {
    'SEEDING_FINISH_REMINDER': 'SEEDING_FINISH_REMINDER',
}

ALERT_TYPES_FIELDWORK = {
    'EVIDENCE_MENTION': 'EVIDENCE_MENTION',
    'EVIDENCE_REPLY': 'EVIDENCE_REPLY',
    'REQUIREMENT_MENTION': 'REQUIREMENT_MENTION',
    'REQUIREMENT_REPLY': 'REQUIREMENT_REPLY',
    'POPULATION_MENTION': 'POPULATION_MENTION',
    'POPULATION_REPLY': 'POPULATION_REPLY',
}

ALERT_TYPES_CONTROL = {
    'CONTROL_MENTION': 'CONTROL_MENTION',
    'CONTROL_REPLY': 'CONTROL_REPLY',
}

ALERT_TYPES_POLICY = {
    'POLICY_MENTION': 'POLICY_MENTION',
    'POLICY_REPLY': 'POLICY_REPLY',
}

ALERT_TYPES_ACTION_ITEM = {
    'CONTROL_ACTION_ITEM_ASSIGNMENT': 'CONTROL_ACTION_ITEM_ASSIGNMENT',
    'CONTROL_PAST_DUE_ACTION_ITEM': 'CONTROL_PAST_DUE_ACTION_ITEM',
    'CONTROL_FUTURE_DUE_ACTION_ITEM': 'CONTROL_FUTURE_DUE_ACTION_ITEM',
}

ALERT_TYPES_DRAFT_REPORT_AUDITOR = {
    'ORG_APPROVED_DRAFT_REPORT': 'ORG_APPROVED_DRAFT_REPORT',
    'ORG_SUGGESTED_DRAFT_EDITS': 'ORG_SUGGESTED_DRAFT_EDITS',
}

ALERT_TYPES_DRAFT_REPORT_USER = {
    'AUDITOR_PUBLISHED_DRAFT_REPORT': 'AUDITOR_PUBLISHED_DRAFT_REPORT',
    'AUDITEE_DRAFT_REPORT_MENTION': 'AUDITEE_DRAFT_REPORT_MENTION',
}

ALERT_TYPES_LAIKA_OBJECTS = {
    'LO_BACKGROUND_CHECK_CHANGED_STATUS': 'LO_BACKGROUND_CHECK_CHANGED_STATUS',
    'LO_BACKGROUND_CHECK_SINGLE_MATCH_LO_TO_USER': (
        'LO_BACKGROUND_CHECK_SINGLE_MATCH_LO_TO_USER'
    ),
    'LO_BACKGROUND_CHECK_MULTIPLE_MATCH_LO_TO_USER': (
        'LO_BACKGROUND_CHECK_MULTIPLE_MATCH_LO_TO_USER'
    ),
}

ALERT_TYPE_USER = {
    'LO_BACKGROUND_CHECK_SINGLE_MATCH_USER_TO_LO': (
        'LO_BACKGROUND_CHECK_SINGLE_MATCH_USER_TO_LO'
    ),
    'LO_BACKGROUND_CHECK_MULTIPLE_MATCH_USER_TO_LO': (
        'LO_BACKGROUND_CHECK_MULTIPLE_MATCH_USER_TO_LO'
    ),
}

ALERT_TYPES_BACKGROUND_CHECK = {
    'LO_BACKGROUND_CHECK_ACCOUNT_CREDENTIALED': (
        'LO_BACKGROUND_CHECK_ACCOUNT_CREDENTIALED'
    ),
    'LO_BACKGROUND_CHECK_TOKEN_DEAUTHORIZED': 'LO_BACKGROUND_CHECK_TOKEN_DEAUTHORIZED',
}

ALERT_TYPES_ACCESS_REVIEW = {
    'ACCESS_REVIEW_START': 'ACCESS_REVIEW_START',
    'ACCESS_REVIEW_COMPLETE': 'ACCESS_REVIEW_COMPLETE',
}

ALERT_TYPES = {
    **ALERT_TYPES_COMMENT,
    **ALERT_TYPES_TASK,
    **ALERT_TYPES_AUDIT_USER,
    **ALERT_TYPES_AUDITOR,
    **ALERT_TYPES_DISCOVERY,
    **ALERT_TYPES_TRAINING,
    **ALERT_TYPES_CX,
    **ALERT_TYPES_FIELDWORK,
    **ALERT_TYPES_CONTROL,
    **ALERT_TYPES_POLICY,
    **ALERT_TYPES_ACTION_ITEM,
    **ALERT_TYPES_DRAFT_REPORT_AUDITOR,
    **ALERT_TYPES_DRAFT_REPORT_USER,
    **ALERT_TYPES_LAIKA_OBJECTS,
    **ALERT_TYPE_USER,
    **ALERT_TYPES_BACKGROUND_CHECK,
    **ALERT_TYPES_ACCESS_REVIEW,
}


ALERT_EMAIL_SUBJECTS_AUDITOR = {
    'ORG_REQUESTED_AUDIT': '[CompanyName] requested a [AuditType] audit.',
    'ORG_COMPLETED_INITIATION': (
        '[CompanyName] completed the initiated stage for their [AuditType] audit.'
    ),
    'ORG_COMPLETED_DRAFT_REPORT': (
        '[CompanyName] completed the draft report stage for their [AuditType] audit.'
    ),
}

ALERT_EMAIL_SUBJECTS_AUDIT = {
    'AUDIT_REQUESTED': '[CompanyName] requested a [AuditType] audit.',
    'AUDIT_INITIATED': 'Your [AuditType] audit is ready to be initiated!',
    'AUDIT_INITIATED_COMPLETED': (
        '[CompanyName] completed the initiated stage for their [AuditType] audit.'
    ),
    'FIELDWORK_INITIATED': 'Your [AuditType] audit is ready for Fieldwork!',
    'DRAFT_REPORT_AVAILABLE': 'Your Draft Report is available for review.',
    'DRAFT_REPORT_COMPLETED': (
        '[CompanyName] completed the draft report stage for their [AuditType] audit.'
    ),
    'AUDIT_COMPLETE': 'Your [AuditType] Audit is now complete.',
}

ALERT_EMAIL_SUBJECTS_COMMENT = {
    'MENTION': '[User] mentioned you in a comment in [TaskName].',
    'REPLY': '[User] replied to your comment in [TaskName].',
    'RESOLVE': '[User] has resolved a comment in [TaskName].',
}

ALERT_EMAIL_SUBJECTS_EVIDENCE = {
    'EVIDENCE_MENTION': (
        '[User] mentioned you in a comment '
        'in [EvidenceName] for your [AuditName] Audit.'
    ),
    'EVIDENCE_REPLY': (
        '[User] replied to your comment in [EvidenceName] for your [AuditName] Audit.'
    ),
}

ALERT_EMAIL_SUBJECTS_CONTROL = {
    'CONTROL_MENTION': '[User] mentioned you in a comment in [ControlName].',
    'CONTROL_REPLY': '[User] replied to your comment in [ControlName].',
}

ALERT_EMAIL_SUBJECTS_POLICY = {
    'POLICY_MENTION': '[User] mentioned you in a comment in [PolicyName].',
    'POLICY_REPLY': '[User] replied to your comment in [PolicyName].',
}

ALERT_EMAIL_SUBJECTS = {
    **ALERT_EMAIL_SUBJECTS_COMMENT,
    **ALERT_EMAIL_SUBJECTS_AUDIT,
    **ALERT_EMAIL_SUBJECTS_AUDITOR,
    **ALERT_EMAIL_SUBJECTS_EVIDENCE,
}

AUDITOR_ALERT_EMAIL_CONTENT = {
    'ORG_REQUESTED_AUDIT': (
        'The details of their audit are available for review. '
        'Log in to share initiation documents and kickoff '
        'calendar with [CompanyName].'
    ),
    'ORG_COMPLETED_INITIATION': (
        'The initiation documents and a proposed time for your '
        'kickoff meeting are now available for review. '
        'Log in to confirm and start the fieldwork stage.'
    ),
    'ORG_COMPLETED_DRAFT_REPORT': (
        'The draft report and reporting documentation now '
        'available for review. Log in to review and start '
        'the final report stage.'
    ),
}


AUDIT_ALERT_EMAIL_CONTENT = {
    'AUDIT_REQUESTED': (
        'The details of their audit are available for review. '
        'Log in to share initiation documents and '
        'kickoff calendar with [CompanyName].'
    ),
    'AUDIT_INITIATED': (
        'The details of your audit are now confirmed. '
        'Log in to sign additional documents and schedule '
        'a kickoff call with your auditor.'
    ),
    'AUDIT_INITIATED_AUDITOR': (
        'The initiation documents and a proposed '
        'time for your kickoff meeting are now '
        'available for review. Log in to confirm '
        'and start the fieldwork stage.'
    ),
    'FIELDWORK_INITIATED': (
        'It\'s time to hand off your evidence for '
        'testing and review. Your Customer Experience '
        'Team is working closely with the auditor and '
        'will follow up with any additional requests. '
        'You will be notified when the draft '
        'report is ready for review.'
    ),
    'DRAFT_REPORT_AVAILABLE': (
        'A new Draft Report for [CompanyName]\'s audit '
        'has been delivered. Log in to review and '
        'approve your draft report. If you have any '
        'questions upon reviewing, schedule a call '
        'with your auditor.'
    ),
    'DRAFT_REPORT_COMPLETED': (
        'The draft report and reporting documentation'
        ' now available for review. Log in to review '
        'and start the final report stage. '
    ),
    'AUDIT_COMPLETE': (
        'Congratulations! The Final Report for [CompanyName]\'s '
        'audit has been delivered. Log in to download '
        'your report.'
    ),
}

AUDIT_ALERT_EMAIL_CTA_AUDIT = {
    'AUDIT_INITIATED': 'COMPLETE AUDIT INITIATION',
    'FIELDWORK_INITIATED': 'COMPLETE AUDIT INITIATION',
    'DRAFT_REPORT_AVAILABLE': 'REVIEW DRAFT REPORT',
    'AUDIT_COMPLETE': 'DOWNLOAD FINAL REPORT',
}

AUDIT_ALERT_EMAIL_CTA_AUDITOR = {
    'ORG_REQUESTED_AUDIT': 'COMPLETE AUDIT REQUEST',
    'ORG_COMPLETED_INITIATION': 'COMPLETE AUDIT INITIATED',
    'ORG_COMPLETED_DRAFT_REPORT': 'COMPLETE FINAL REPORT',
}

AUDIT_ALERT_EMAIL_CTA = {
    **AUDIT_ALERT_EMAIL_CTA_AUDIT,
    **AUDIT_ALERT_EMAIL_CTA_AUDITOR,
}

ALERT_EMAIL_TEMPLATES = {
    'COMMENTS': 'alert_email.html',
    'AUDITS': 'alert_oca_email.html',
    'AUDITOR': 'alert_auditor_oca_email.html',
    'EVIDENCE_COMMENTS': 'alert_evidence_comment.html',
    'EVIDENCE_COMMENTS_AUDITOR': 'alert_evidence_comment_auditor.html',
}

PERSONAL_ALERTS = {
    'MENTION': 'MENTION',
    'REPLY': 'REPLY',
    'NEW_ASSIGNMENT': 'NEW_ASSIGNMENT',
    'TRAINING_REMINDER': 'TRAINING_REMINDER',
    'CONTROL_MENTION': 'CONTROL_MENTION',
    'CONTROL_REPLY': 'CONTROL_REPLY',
}

SLACK_AUDIT_ALERTS = {
    'AUDIT_REQUESTED': 'AUDIT_REQUESTED',
    'AUDIT_INITIATED': 'AUDIT_INITIATED',
    'DRAFT_REPORT_AVAILABLE': 'DRAFT_REPORT_AVAILABLE',
    'AUDIT_COMPLETE': 'AUDIT_COMPLETE',
}

(SEEDING_FINISH_REMINDER,) = ALERT_TYPES_CX.values()

ALERTS_MAX_NUMBER = 3

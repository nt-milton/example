from audit.constants import CURRENT_AUDIT_STATUS
from audit.utils.audit import get_current_status


def draft_report_stage_completed(audit_status):
    requirements = [
        audit_status.review_draft_report_checked,
        audit_status.representation_letter_checked,
        audit_status.management_assertion_checked,
        audit_status.subsequent_events_questionnaire_checked,
    ]

    return all(requirement for requirement in requirements)


def initiated_stage_completed(audit_status):
    requirements = [
        audit_status.engagement_letter_checked,
        audit_status.control_design_assessment_checked,
        audit_status.kickoff_meeting_checked,
    ]

    return all(requirement for requirement in requirements)


def audit_stage_is_completed(audit_status):
    current_status = get_current_status(audit_status)
    if current_status == CURRENT_AUDIT_STATUS['IN_DRAFT_REPORT']:
        return draft_report_stage_completed(audit_status)
    elif current_status == CURRENT_AUDIT_STATUS['INITIATED']:
        return initiated_stage_completed(audit_status)

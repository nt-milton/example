from audit.constants import DRAFT_REPORT_STAGE_CHECKS, INITIATED_STAGE_CHECKS


def update_status_checkboxes(status):
    if not status.initiated:
        for check in INITIATED_STAGE_CHECKS:
            setattr(status, check, False)

    if not status.in_draft_report:
        for check in DRAFT_REPORT_STAGE_CHECKS:
            setattr(status, check, False)

import pytest

from audit.models import AuditStatus
from audit.utils.admin import update_status_checkboxes


@pytest.mark.parametrize(
    'initiated,draft_report,engagement_letter,control_design_assessment,'
    'kickoff_meeting,final_engagement_letter,'
    'final_control_design_assessment,final_kickoff_meeting',
    [
        (False, False, True, True, True, False, False, False),
        (False, False, True, False, False, False, False, False),
        (True, False, True, True, False, True, True, False),
    ],
)
def test_update_status_checkboxes(
    initiated,
    draft_report,
    engagement_letter,
    control_design_assessment,
    kickoff_meeting,
    final_engagement_letter,
    final_control_design_assessment,
    final_kickoff_meeting,
):
    status = AuditStatus(
        initiated=initiated,
        in_draft_report=draft_report,
        engagement_letter_checked=engagement_letter,
        control_design_assessment_checked=control_design_assessment,
        kickoff_meeting_checked=kickoff_meeting,
    )

    update_status_checkboxes(status)
    assert status.engagement_letter_checked is final_engagement_letter
    assert status.control_design_assessment_checked is final_control_design_assessment
    assert status.kickoff_meeting_checked is final_kickoff_meeting

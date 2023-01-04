import pytest

from ..models import DraftReportComment


@pytest.mark.functional(permissions=['audit.view_draftreportcomment'])
def test_draft_report_comment_model(audit, graphql_user, graphql_audit_user):
    DraftReportComment.objects.custom_create(
        owner=graphql_user,
        content='New comment',
        audit_id=audit.id,
        tagged_users=[graphql_audit_user.email],
        page=1,
    )

    draft_report_comments = DraftReportComment.objects.all()
    assert len(draft_report_comments) == 1

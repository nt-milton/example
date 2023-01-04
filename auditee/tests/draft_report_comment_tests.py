import pytest

from alert.constants import ALERT_TYPES
from alert.models import Alert
from audit.models import AuditAlert, AuditAuditor, DraftReportComment
from auditee.tests.mutations import CREATE_NOTIFICATION_REVIEWED_DRAFT_REPORT
from auditee.tests.queries import (
    GET_AUDITEE_ALERTS,
    GET_DRAFT_REPORT_COMMENTS,
    GET_DRAFT_REPORT_MENTIONS_USERS,
)
from comment.models import ReplyAlert


@pytest.fixture
def draft_report_comment(graphql_user, audit, comment):
    return DraftReportComment.objects.create(audit=audit, comment=comment, page=2)


@pytest.fixture
def resolved_draft_report_comment(graphql_user, audit, resolved_comment):
    return DraftReportComment.objects.create(
        audit=audit, comment=resolved_comment, page=2
    )


@pytest.mark.functional(permissions=['audit.view_draftreportcomment'])
def test_get_draft_report_comments(
    graphql_client,
    laika_admin_user,
    draft_report_comment,
    resolved_draft_report_comment,
    audit,
):
    response = graphql_client.execute(
        GET_DRAFT_REPORT_COMMENTS, variables={'auditId': audit.id}
    )

    assert len(response['data']['auditeeDraftReportComments']) == 2


@pytest.mark.functional(permissions=['audit.view_draftreportcomment'])
def test_get_draft_report_mentions_users(
    graphql_client, laika_super_admin, laika_admin_user, auditor_user, audit
):
    AuditAuditor.objects.create(
        audit=audit, auditor=auditor_user, title_role='lead_auditor'
    )
    response = graphql_client.execute(
        GET_DRAFT_REPORT_MENTIONS_USERS, variables={'auditId': audit.id}
    )

    assert len(response['data']['auditeeDraftReportMentionsUsers']) == 3


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_get_draft_report_mention_alerts(
    graphql_client, graphql_user, auditor_user, draft_report_comment, reply
):
    alert = Alert.objects.create(
        sender=auditor_user.user,
        receiver=graphql_user,
        type=ALERT_TYPES['AUDITEE_DRAFT_REPORT_MENTION'],
    )

    ReplyAlert.objects.create(alert=alert, reply=reply)

    response = graphql_client.execute(GET_AUDITEE_ALERTS)

    assert len(response['data']['alerts']['data']) == 1


@pytest.mark.functional(permissions=['audit.change_draftreportcomment'])
def test_notify_auditor_suggested_edits(
    graphql_client, laika_admin_user, draft_report_comment
):
    response = graphql_client.execute(
        CREATE_NOTIFICATION_REVIEWED_DRAFT_REPORT,
        variables={
            'input': dict(
                auditId=draft_report_comment.audit.id,
            )
        },
    )

    assert (
        response['data']['createAuditeeNotificationReviewedDraftReport'][
            'draftReportComments'
        ][0]['auditorNotified']
        is True
    )


@pytest.mark.functional(permissions=['audit.change_draftreportcomment'])
def test_notify_auditor_alerts(
    graphql_client, laika_admin_user, draft_report_comment, auditor_user, audit_auditor
):
    graphql_client.execute(
        CREATE_NOTIFICATION_REVIEWED_DRAFT_REPORT,
        variables={
            'input': dict(
                auditId=draft_report_comment.audit.id,
            )
        },
    )

    audit_alert = AuditAlert.objects.all()
    assert len(audit_alert) == 1

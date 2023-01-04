import pytest

from alert.models import Alert
from audit.models import AuditAuditor, DraftReportComment
from auditor.tests.mutations import (
    CREATE_AUDITOR_DRAFT_REPORT_REPLY,
    DELETE_AUDITOR_DRAFT_REPORT_REPLY,
    UPDATE_AUDITOR_DRAFT_REPORT_REPLY,
)
from auditor.tests.queries import (
    GET_DRAFT_REPORT_COMMENT,
    GET_DRAFT_REPORT_MENTIONS_USERS,
)
from comment.models import Reply
from user.constants import AUDITOR_ROLES

COMMENT_CONTENT = 'This is a comment'
REPLY_CONTENT = 'This is a reply'
REPLY_CONTENT_TO_UPDATE = 'Reply updated'


@pytest.fixture
def draft_report_comment(graphql_audit_user, audit, jarvis_comment):
    DraftReportComment.objects.create(audit=audit, comment=jarvis_comment)

    return jarvis_comment


@pytest.fixture
def draft_resolved_comment(graphql_audit_user, audit, jarvis_resolved_comment):
    DraftReportComment.objects.create(audit=audit, comment=jarvis_resolved_comment)

    return jarvis_resolved_comment


@pytest.mark.functional(permissions=['audit.view_draftreportcomment'])
def test_get_draft_report_comments(
    graphql_audit_client, audit, draft_report_comment, jarvis_reply
):
    response = graphql_audit_client.execute(
        GET_DRAFT_REPORT_COMMENT, variables={'auditId': audit.id}
    )

    comments = response['data']['auditorDraftReportComments']
    assert len(comments) == 1


@pytest.mark.functional(permissions=['audit.add_draftreportcomment'])
def test_add_draft_report_reply(
    graphql_audit_client, graphql_audit_user, audit, draft_report_comment
):
    graphql_audit_user.role = AUDITOR_ROLES['AUDITOR']
    graphql_audit_user.save()
    add_reply_input = {
        'input': dict(
            commentId=draft_report_comment.id, auditId=audit.id, content=REPLY_CONTENT
        )
    }

    graphql_audit_client.execute(
        CREATE_AUDITOR_DRAFT_REPORT_REPLY, variables=add_reply_input
    )

    assert Reply.objects.count() == 1


@pytest.mark.functional(permissions=['audit.change_draftreportcomment'])
def test_update_draft_report_reply(
    graphql_audit_client,
    draft_report_comment,
    jarvis_reply,
    audit,
):
    assert jarvis_reply.content == REPLY_CONTENT
    graphql_audit_client.execute(
        UPDATE_AUDITOR_DRAFT_REPORT_REPLY,
        variables={
            'input': dict(
                auditId=audit.id,
                replyId=jarvis_reply.id,
                commentId=draft_report_comment.id,
                content=REPLY_CONTENT_TO_UPDATE,
            )
        },
    )

    reply = Reply.objects.get(id=jarvis_reply.id)
    assert reply.content == REPLY_CONTENT_TO_UPDATE


@pytest.mark.functional(permissions=['audit.delete_draftreportcomment'])
def test_delete_draft_report_reply(
    graphql_audit_client,
    draft_report_comment,
    jarvis_reply,
    audit,
):
    assert not jarvis_reply.is_deleted
    graphql_audit_client.execute(
        DELETE_AUDITOR_DRAFT_REPORT_REPLY,
        variables={
            'input': dict(
                auditId=audit.id,
                replyId=jarvis_reply.id,
                commentId=draft_report_comment.id,
            )
        },
    )

    reply = Reply.objects.get(id=jarvis_reply.id)
    assert reply.is_deleted


@pytest.mark.functional(permissions=['audit.view_draftreportcomment'])
def test_get_draft_report_mentions_users(
    graphql_audit_client, laika_super_admin, laika_admin_user, auditor_user, audit
):
    AuditAuditor.objects.create(
        audit=audit, auditor=auditor_user, title_role='lead_auditor'
    )
    response = graphql_audit_client.execute(
        GET_DRAFT_REPORT_MENTIONS_USERS, variables={'auditId': audit.id}
    )

    assert len(response['data']['auditorDraftReportMentionsUsers']) == 3


@pytest.mark.functional(permissions=['audit.add_draftreportcomment'])
def test_create_draft_report_mention_alert(
    graphql_audit_client,
    audit,
    draft_report_comment,
    graphql_audit_user,
    laika_super_admin,
):
    graphql_audit_user.role = AUDITOR_ROLES['AUDITOR']
    graphql_audit_user.save()
    add_reply_input = {
        'input': dict(
            commentId=draft_report_comment.id,
            auditId=audit.id,
            content=REPLY_CONTENT,
            taggedUsers=[laika_super_admin.email],
        )
    }

    graphql_audit_client.execute(
        CREATE_AUDITOR_DRAFT_REPORT_REPLY, variables=add_reply_input
    )

    assert Alert.objects.count() == 1

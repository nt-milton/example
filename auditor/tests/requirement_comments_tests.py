import pytest
from graphene.test import Client

from audit.models import Audit, AuditAuditor, AuditFirm, AuditorAuditFirm
from comment.models import COMMENT_STATE, Comment
from fieldwork.models import RequirementComment, RequirementEvidence
from organization.models import Organization
from user.constants import AUDITOR, AUDITOR_ADMIN
from user.models import User
from user.tests.factory import create_user_auditor

from .queries import GET_REQUIREMENT_COMMENT, GET_REQUIREMENT_COMMENT_USERS

COMMENT_CONTENT = 'This is a comment'
REPLY_CONTENT = 'This is a reply'
ER_OPEN_STATUS = 'open'


@pytest.fixture
def req_comment(requirement, jarvis_comment):
    RequirementComment.objects.create(requirement=requirement, comment=jarvis_comment)

    return jarvis_comment


@pytest.fixture
def requirement_evidence(evidence, requirement):
    return RequirementEvidence.objects.create(
        evidence=evidence, requirement=requirement
    )


@pytest.mark.functional(permissions=['fieldwork.view_requirementcomment'])
def test_get_requirement_comments(
    graphql_audit_client, requirement, req_comment, jarvis_reply
):
    graphql_audit_client.execute(
        GET_REQUIREMENT_COMMENT, variables={'requirementId': str(requirement.id)}
    )
    assert Comment.objects.count() == 1


COMMENT_CONTENT_TO_UPDATE = 'Updated comment'
REPLY_CONTENT_TO_UPDATE = 'Updated reply'
comment_state = dict(COMMENT_STATE)


@pytest.mark.functional(permissions=['fieldwork.view_requirement'])
def test_get_requirement_comment_users(
    graphql_audit_client: Client,
    graphql_organization: Organization,
    graphql_audit_user: User,
    graphql_audit_firm: AuditFirm,
    audit: Audit,
):
    auditor_admin_not_in_audit = create_user_auditor(
        email="test1@heylaika.com", role=AUDITOR_ADMIN
    )
    auditor = create_user_auditor(email="test2@heylaika.com", role=AUDITOR)
    auditor_admin_in_audit = create_user_auditor(
        email="test3@heylaika.com", role=AUDITOR_ADMIN
    )

    AuditorAuditFirm.objects.create(
        auditor=auditor_admin_not_in_audit, audit_firm=graphql_audit_firm
    )
    AuditorAuditFirm.objects.create(auditor=auditor, audit_firm=graphql_audit_firm)
    AuditorAuditFirm.objects.create(
        auditor=auditor_admin_in_audit, audit_firm=graphql_audit_firm
    )
    AuditorAuditFirm.objects.create(
        auditor=graphql_audit_user.auditor, audit_firm=graphql_audit_firm
    )

    AuditAuditor.objects.create(audit=audit, auditor=auditor_admin_in_audit)

    response = graphql_audit_client.execute(
        GET_REQUIREMENT_COMMENT_USERS, variables={'auditId': str(audit.id)}
    )

    assert len(response['data']['auditorRequirementCommentUsers']) == 3

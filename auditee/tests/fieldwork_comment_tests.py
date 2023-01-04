import pytest
from graphene.test import Client

from alert.constants import ALERT_TYPES
from alert.models import Alert
from audit.models import Audit, AuditAuditor, AuditFirm
from auditor.tests.factory import create_evidence_comment_with_pool
from comment.models import Comment, ReplyAlert
from fieldwork.models import EvidenceComment
from fieldwork.types import EvidenceCommentPoolsEnum
from organization.models import Organization
from user.constants import AUDITOR, ROLE_ADMIN, ROLE_SUPER_ADMIN
from user.models import Auditor, User
from user.tests import create_user_auditor

from .factory import create_evidence_mention_alert
from .queries import (
    GET_AUDITEE_ALERTS,
    GET_AUDITEE_EVIDENCE_COMMENT_USERS,
    GET_AUDITEE_EVIDENCE_COMMENTS_BY_POOL,
)


@pytest.fixture
def auditor_user_in_audit_team(
    graphql_organization: Organization, graphql_audit_firm: AuditFirm, audit: Audit
) -> Auditor:
    auditor = create_user_auditor(
        email='auditor_user_in_team@heylaika.com',
        role=AUDITOR,
        with_audit_firm=True,
        audit_firm=graphql_audit_firm.name,
    )
    AuditAuditor.objects.create(auditor=auditor, audit=audit)
    return auditor


COMMENT_CONTENT = 'My comment'


@pytest.fixture
def evidence_request_comment(graphql_user, evidence, comment):
    EvidenceComment.objects.create(evidence=evidence, comment=comment, pool='all')
    return comment


@pytest.fixture
def comment_lcl(graphql_user, evidence, laika_admin_user):
    return create_evidence_comment_with_pool(
        owner=laika_admin_user,
        content=COMMENT_CONTENT,
        evidence=evidence,
        pool='lcl-cx',
    )


@pytest.fixture
def comment_laika(graphql_user, evidence, laika_admin_user):
    return create_evidence_comment_with_pool(
        owner=laika_admin_user, content=COMMENT_CONTENT, evidence=evidence, pool='laika'
    )


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_laika_pool_evidence_comment_users_by_super_admin(
    graphql_client: Client,
    graphql_user: User,
    auditor_user: Auditor,
    auditor_admin_user: Auditor,
    laika_admin_user: User,
    auditor_user_in_audit_team: Auditor,
    audit: Audit,
):
    graphql_user.role = ROLE_SUPER_ADMIN
    graphql_user.save()

    response_users_laika_pool = graphql_client.execute(
        GET_AUDITEE_EVIDENCE_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': EvidenceCommentPoolsEnum.Laika.name},
    )

    users = response_users_laika_pool['data']['auditeeEvidenceCommentUsers']
    assert len(users) == 2


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_all_pool_evidence_comment_users_by_super_admin(
    graphql_client: Client,
    graphql_user: User,
    auditor_user: Auditor,
    auditor_admin_user: Auditor,
    laika_admin_user: User,
    auditor_user_in_audit_team: Auditor,
    audit: Audit,
):
    graphql_user.role = ROLE_SUPER_ADMIN
    graphql_user.save()

    response_users_all_pool = graphql_client.execute(
        GET_AUDITEE_EVIDENCE_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': EvidenceCommentPoolsEnum.All.name},
    )

    users = response_users_all_pool['data']['auditeeEvidenceCommentUsers']
    assert len(users) == 4


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_lcl_cx_pool_evidence_comment_users_by_super_admin(
    graphql_client: Client,
    graphql_user: User,
    auditor_user: Auditor,
    auditor_admin_user: Auditor,
    laika_admin_user: User,
    auditor_user_in_audit_team: Auditor,
    audit: Audit,
):
    graphql_user.role = ROLE_SUPER_ADMIN
    graphql_user.save()

    response_users_lcl_cx_pool = graphql_client.execute(
        GET_AUDITEE_EVIDENCE_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': EvidenceCommentPoolsEnum.LCL_CX.name},
    )

    users = response_users_lcl_cx_pool['data']['auditeeEvidenceCommentUsers']
    assert len(users) == 3


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_lcl_pool_evidence_comment_users_by_super_admin(
    graphql_client: Client,
    graphql_user: User,
    auditor_user: Auditor,
    auditor_admin_user: Auditor,
    laika_admin_user: User,
    auditor_user_in_audit_team: Auditor,
    audit: Audit,
):
    graphql_user.role = ROLE_SUPER_ADMIN
    graphql_user.save()

    response_users_lcl_pool = graphql_client.execute(
        GET_AUDITEE_EVIDENCE_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': EvidenceCommentPoolsEnum.LCL.name},
    )

    users = response_users_lcl_pool['data']['auditeeEvidenceCommentUsers']
    assert users is None


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_laika_pool_evidence_comment_users_by_organization_admin(
    graphql_client: Client,
    graphql_user: User,
    auditor_user: Auditor,
    auditor_admin_user: Auditor,
    laika_admin_user: User,
    auditor_user_in_audit_team: Auditor,
    audit: Audit,
):
    graphql_user.role = ROLE_ADMIN
    graphql_user.save()

    laika_admin_user.role = ROLE_SUPER_ADMIN
    laika_admin_user.save()

    response_users_laika_pool = graphql_client.execute(
        GET_AUDITEE_EVIDENCE_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': EvidenceCommentPoolsEnum.Laika.name},
    )

    users = response_users_laika_pool['data']['auditeeEvidenceCommentUsers']
    assert len(users) == 2


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_all_pool_evidence_comment_users_by_organization_admin(
    graphql_client: Client,
    graphql_user: User,
    auditor_user: Auditor,
    auditor_admin_user: Auditor,
    laika_admin_user: User,
    auditor_user_in_audit_team: Auditor,
    audit: Audit,
):
    graphql_user.role = ROLE_ADMIN
    graphql_user.save()

    laika_admin_user.role = ROLE_SUPER_ADMIN
    laika_admin_user.save()

    response_users_all_pool = graphql_client.execute(
        GET_AUDITEE_EVIDENCE_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': EvidenceCommentPoolsEnum.All.name},
    )

    users = response_users_all_pool['data']['auditeeEvidenceCommentUsers']
    assert len(users) == 4


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_lcl_cx_pool_evidence_comment_users_by_organization_admin(
    graphql_client: Client,
    graphql_user: User,
    auditor_user: Auditor,
    auditor_admin_user: Auditor,
    laika_admin_user: User,
    auditor_user_in_audit_team: Auditor,
    audit: Audit,
):
    graphql_user.role = ROLE_ADMIN
    graphql_user.save()

    laika_admin_user.role = ROLE_SUPER_ADMIN
    laika_admin_user.save()

    response_users_lcl_cx_pool = graphql_client.execute(
        GET_AUDITEE_EVIDENCE_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': EvidenceCommentPoolsEnum.LCL_CX.name},
    )

    users = response_users_lcl_cx_pool['data']['auditeeEvidenceCommentUsers']
    assert users is None


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_lcl_pool_evidence_comment_users_by_organization_admin(
    graphql_client: Client,
    graphql_user: User,
    auditor_user: Auditor,
    auditor_admin_user: Auditor,
    laika_admin_user: User,
    auditor_user_in_audit_team: Auditor,
    audit: Audit,
):
    graphql_user.role = ROLE_ADMIN
    graphql_user.save()

    laika_admin_user.role = ROLE_SUPER_ADMIN
    laika_admin_user.save()

    response_users_lcl_pool = graphql_client.execute(
        GET_AUDITEE_EVIDENCE_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': EvidenceCommentPoolsEnum.LCL.name},
    )

    users = response_users_lcl_pool['data']['auditeeEvidenceCommentUsers']
    assert users is None


def create_comments(user, evidence):
    internal_comments = [True, True, False]

    for internal_comment in internal_comments:
        comment = Comment.objects.create(owner=user, content=COMMENT_CONTENT)
        EvidenceComment.objects.create(
            evidence=evidence, comment=comment, is_internal_comment=internal_comment
        )


@pytest.mark.functional(permissions=['fieldwork.view_evidencecomment'])
def test_get_auditee_evidence_comments_by_pool(
    graphql_client, laika_admin_user, evidence
):
    EvidenceComment.objects.custom_create(
        owner=laika_admin_user,
        evidence_id=evidence.id,
        tagged_users=[],
        content=COMMENT_CONTENT,
        is_internal_comment=True,
        pool=EvidenceCommentPoolsEnum.Laika.value,
    )
    response = graphql_client.execute(
        GET_AUDITEE_EVIDENCE_COMMENTS_BY_POOL,
        variables={
            'auditId': evidence.audit.id,
            'evidenceId': evidence.id,
            'pool': EvidenceCommentPoolsEnum.Laika.name,
        },
    )
    assert len(response['data']['auditeeEvidenceComments']) == 1


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_all_comment_alert(
    graphql_client,
    graphql_user,
    audit,
    laika_admin_user,
    evidence_request_comment,
    reply,
):
    create_evidence_mention_alert(
        laika_admin_user, evidence_request_comment, graphql_user
    )
    reply_alert = Alert.objects.create(
        sender=laika_admin_user,
        receiver=graphql_user,
        type=ALERT_TYPES['EVIDENCE_REPLY'],
    )

    ReplyAlert.objects.create(
        alert=reply_alert,
        reply=reply,
    )

    mention_alert = Alert.objects.create(
        sender=laika_admin_user,
        receiver=graphql_user,
        type=ALERT_TYPES['EVIDENCE_MENTION'],
    )

    ReplyAlert.objects.create(
        alert=mention_alert,
        reply=reply,
    )

    response = graphql_client.execute(GET_AUDITEE_ALERTS)
    alert_response = response['data']['alerts']['data']
    assert alert_response[0]['commentPool'] == 'all'
    assert len(alert_response) == 3


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_laika_comment_alert(
    graphql_client, graphql_user, audit, laika_admin_user, comment_laika, reply
):
    create_evidence_mention_alert(laika_admin_user, comment_laika, graphql_user)

    response = graphql_client.execute(GET_AUDITEE_ALERTS)
    alert_response = response['data']['alerts']['data']

    assert alert_response[0]['commentPool'] == 'laika'
    assert len(alert_response) == 1


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_lcl_comment_alert(
    graphql_client, graphql_user, audit, laika_admin_user, comment_lcl, reply
):
    create_evidence_mention_alert(laika_admin_user, comment_lcl, graphql_user)

    response = graphql_client.execute(GET_AUDITEE_ALERTS)
    alert_response = response['data']['alerts']['data']
    assert alert_response[0]['commentPool'] == 'lcl-cx'
    assert len(alert_response) == 1

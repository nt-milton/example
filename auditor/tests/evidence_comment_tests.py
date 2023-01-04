import pytest
from graphene.test import Client

from alert.constants import ALERT_TYPES
from alert.models import Alert
from audit.models import Audit, AuditAuditor, AuditFirm, AuditorAuditFirm
from auditee.tests.factory import create_evidence_mention_alert
from comment.models import Comment, ReplyAlert
from fieldwork.models import Evidence, EvidenceComment
from fieldwork.types import EvidenceCommentPoolsEnum
from user.constants import AUDITOR, AUDITOR_ROLES, ROLE_SUPER_ADMIN
from user.models import Auditor, User
from user.tests import create_user_auditor

from .factory import create_evidence_comment_with_pool
from .mutations import ADD_AUDITOR_COMMENT
from .queries import GET_AUDITOR_ALERTS, GET_AUDITOR_EVIDENCE_COMMENT_USERS

REPLY_CONTENT = 'My reply'


@pytest.fixture
def auditor_user_in_audit_team(graphql_audit_firm: AuditFirm, audit: Audit) -> Auditor:
    auditor = create_user_auditor(
        email='auditor_user_in_team@heylaika.com',
        role=AUDITOR,
        with_audit_firm=True,
        audit_firm=graphql_audit_firm.name,
    )
    AuditAuditor.objects.create(auditor=auditor, audit=audit)
    return auditor


COMMENT_CONTENT = 'Comment content'


@pytest.fixture
def evidence_comment(graphql_audit_user, evidence, jarvis_comment):
    EvidenceComment.objects.create(
        evidence=evidence, comment=jarvis_comment, pool='all'
    )
    return jarvis_comment


@pytest.fixture
def comment_lcl(graphql_audit_user, evidence, auditor_user):
    return create_evidence_comment_with_pool(
        owner=auditor_user.user, content=COMMENT_CONTENT, evidence=evidence, pool='lcl'
    )


@pytest.fixture
def comment_lcl_cx(graphql_audit_user, evidence, auditor_user):
    return create_evidence_comment_with_pool(
        owner=auditor_user.user,
        content=COMMENT_CONTENT,
        evidence=evidence,
        pool='lcl-cx',
    )


def create_auditor_comments(auditor, evidence):
    internal_comments = [True, True, False, False, False]

    for internal_comment in internal_comments:
        comment = Comment.objects.create(owner=auditor, content=COMMENT_CONTENT)
        EvidenceComment.objects.create(
            evidence=evidence, comment=comment, is_internal_comment=internal_comment
        )


def create_user_comments(laika_super_admin: User, evidence: Evidence):
    internal_comments = [True, True, False]

    for internal_comment in internal_comments:
        comment = Comment.objects.create(
            owner=laika_super_admin, content=COMMENT_CONTENT
        )
        EvidenceComment.objects.create(
            evidence=evidence, comment=comment, is_internal_comment=internal_comment
        )


@pytest.mark.functional(
    permissions=['fieldwork.add_evidencecomment', 'comment.add_comment']
)
def test_delete_evidence_alerts(
    graphql_audit_client, evidence, graphql_audit_user, auditor_user, evidence_comment
):
    add_comment_input = {
        'input': dict(
            content=COMMENT_CONTENT,
            taggedUsers=[auditor_user.user.email],
            objectType='fieldwork_evidence',
            objectId=evidence.id,
        )
    }
    graphql_audit_user.role = AUDITOR_ROLES['AUDITOR']
    graphql_audit_user.save()
    graphql_audit_client.execute(ADD_AUDITOR_COMMENT, variables=add_comment_input)

    alerts = Alert.objects.all()
    assert len(alerts) == 1
    evidence.delete()
    alerts = Alert.objects.all()
    assert len(alerts) == 0


@pytest.mark.functional(
    permissions=['fieldwork.add_evidencecomment', 'comment.add_comment']
)
def test_add_evidence_comment_infering_pool(
    graphql_audit_client, graphql_audit_user, evidence
):
    add_comment_input = {
        'input': dict(
            objectId=evidence.id,
            content=COMMENT_CONTENT,
            objectType='fieldwork_evidence',
        )
    }

    response = graphql_audit_client.execute(
        ADD_AUDITOR_COMMENT, variables=add_comment_input
    )
    evidence_comment = EvidenceComment.objects.get(
        comment__id=response['data']['addAuditorComment']['comment']['id']
    )
    assert evidence_comment.pool == EvidenceCommentPoolsEnum.All.value


@pytest.mark.functional(permissions=['audit.view_auditalert'])
def test_all_comment_alert(
    graphql_audit_client,
    graphql_audit_user,
    audit,
    auditor_user,
    evidence_comment,
    jarvis_reply,
):
    create_evidence_mention_alert(
        auditor_user.user, evidence_comment, graphql_audit_user
    )
    reply_alert = Alert.objects.create(
        sender=auditor_user.user,
        receiver=graphql_audit_user,
        type=ALERT_TYPES['EVIDENCE_REPLY'],
    )

    ReplyAlert.objects.create(
        alert=reply_alert,
        reply=jarvis_reply,
    )
    response = graphql_audit_client.execute(GET_AUDITOR_ALERTS)
    alert_response = response['data']['auditorAlerts']['alerts']

    assert alert_response[0]['commentPool'] == 'all'
    assert len(alert_response) == 2


@pytest.mark.functional(permissions=['audit.view_auditalert'])
def test_lcl_comment_alert(
    graphql_audit_client,
    graphql_audit_user,
    audit,
    auditor_user,
    comment_lcl,
):
    create_evidence_mention_alert(
        auditor_user.user,
        comment_lcl,
        graphql_audit_user,
    )

    response = graphql_audit_client.execute(GET_AUDITOR_ALERTS)
    alert_response = response['data']['auditorAlerts']['alerts']

    assert alert_response[0]['commentPool'] == 'lcl'
    assert len(alert_response) == 1


@pytest.mark.functional(permissions=['audit.view_auditalert'])
def test_lcl_cx_comment_alert(
    graphql_audit_client,
    graphql_audit_user,
    audit,
    auditor_user,
    comment_lcl_cx,
):
    create_evidence_mention_alert(auditor_user.user, comment_lcl_cx, graphql_audit_user)

    response = graphql_audit_client.execute(GET_AUDITOR_ALERTS)
    alert_response = response['data']['auditorAlerts']['alerts']
    assert alert_response[0]['commentPool'] == 'lcl-cx'
    assert len(alert_response) == 1


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_laika_pool_evidence_comment_users_by_auditor_admin(
    graphql_audit_client: Client,
    graphql_audit_user: User,
    auditor_user_in_audit_team: Auditor,
    auditor_user: User,
    laika_super_admin: User,
    laika_admin_user: User,
    audit: Audit,
):
    response_users_laika_pool = graphql_audit_client.execute(
        GET_AUDITOR_EVIDENCE_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': EvidenceCommentPoolsEnum.Laika.name},
    )
    users = response_users_laika_pool['data']['auditorEvidenceCommentUsers']
    assert users is None


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_all_pool_evidence_comment_users_by_auditor_admin(
    graphql_audit_client: Client,
    graphql_audit_user: User,
    auditor_user_in_audit_team: Auditor,
    auditor_user: User,
    laika_super_admin: User,
    laika_admin_user: User,
    audit: Audit,
):
    response_users_all_pool = graphql_audit_client.execute(
        GET_AUDITOR_EVIDENCE_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': EvidenceCommentPoolsEnum.All.name},
    )

    users = response_users_all_pool['data']['auditorEvidenceCommentUsers']
    assert len(users) == 4


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_lcl_cx_pool_evidence_comment_users_by_auditor_admin(
    graphql_audit_client: Client,
    graphql_audit_user: User,
    auditor_user_in_audit_team: Auditor,
    auditor_user: User,
    laika_super_admin: User,
    laika_admin_user: User,
    audit: Audit,
):
    response_users_lcl_cx_pool = graphql_audit_client.execute(
        GET_AUDITOR_EVIDENCE_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': EvidenceCommentPoolsEnum.LCL_CX.name},
    )

    users = response_users_lcl_cx_pool['data']['auditorEvidenceCommentUsers']
    assert len(users) == 3


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_lcl_pool_evidence_comment_users_by_auditor_admin(
    graphql_audit_client: Client,
    graphql_audit_user: User,
    auditor_user_in_audit_team: Auditor,
    auditor_user: User,
    laika_super_admin: User,
    laika_admin_user: User,
    audit: Audit,
):
    response_users_lcl_pool = graphql_audit_client.execute(
        GET_AUDITOR_EVIDENCE_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': EvidenceCommentPoolsEnum.LCL.name},
    )

    users = response_users_lcl_pool['data']['auditorEvidenceCommentUsers']
    assert len(users) == 2


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_laika_pool_evidence_comment_users_by_auditor(
    graphql_audit_client: Client,
    graphql_audit_user: User,
    auditor_user_in_audit_team: Auditor,
    auditor_user: User,
    laika_super_admin: User,
    laika_admin_user: User,
    audit: Audit,
):
    graphql_audit_user.role = AUDITOR
    graphql_audit_user.save()

    graphql_auditor = Auditor.objects.get(user__id=graphql_audit_user.id)
    AuditorAuditFirm.objects.create(
        auditor=graphql_auditor, audit_firm=audit.audit_firm
    )
    AuditAuditor.objects.create(auditor=graphql_auditor, audit=audit)

    auditor_user_in_audit_team.role = ROLE_SUPER_ADMIN
    auditor_user_in_audit_team.save()

    response_users_laika_pool = graphql_audit_client.execute(
        GET_AUDITOR_EVIDENCE_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': EvidenceCommentPoolsEnum.Laika.name},
    )

    users = response_users_laika_pool['data']['auditorEvidenceCommentUsers']
    assert users is None


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_all_pool_evidence_comment_users_by_auditor(
    graphql_audit_client: Client,
    graphql_audit_user: User,
    auditor_user_in_audit_team: Auditor,
    auditor_user: User,
    laika_super_admin: User,
    laika_admin_user: User,
    audit: Audit,
):
    graphql_audit_user.role = AUDITOR
    graphql_audit_user.save()

    graphql_auditor = Auditor.objects.get(user__id=graphql_audit_user.id)
    AuditorAuditFirm.objects.create(
        auditor=graphql_auditor, audit_firm=audit.audit_firm
    )
    AuditAuditor.objects.create(auditor=graphql_auditor, audit=audit)

    auditor_user_in_audit_team.role = ROLE_SUPER_ADMIN
    auditor_user_in_audit_team.save()

    response_users_all_pool = graphql_audit_client.execute(
        GET_AUDITOR_EVIDENCE_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': EvidenceCommentPoolsEnum.All.name},
    )

    users = response_users_all_pool['data']['auditorEvidenceCommentUsers']
    assert len(users) == 4


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_lcl_cx_pool_evidence_comment_users_by_auditor(
    graphql_audit_client: Client,
    graphql_audit_user: User,
    auditor_user_in_audit_team: Auditor,
    auditor_user: User,
    laika_super_admin: User,
    laika_admin_user: User,
    audit: Audit,
):
    graphql_audit_user.role = AUDITOR
    graphql_audit_user.save()

    graphql_auditor = Auditor.objects.get(user__id=graphql_audit_user.id)
    AuditorAuditFirm.objects.create(
        auditor=graphql_auditor, audit_firm=audit.audit_firm
    )
    AuditAuditor.objects.create(auditor=graphql_auditor, audit=audit)

    auditor_user_in_audit_team.role = ROLE_SUPER_ADMIN
    auditor_user_in_audit_team.save()

    response_users_lcl_cx_pool = graphql_audit_client.execute(
        GET_AUDITOR_EVIDENCE_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': EvidenceCommentPoolsEnum.LCL_CX.name},
    )

    users = response_users_lcl_cx_pool['data']['auditorEvidenceCommentUsers']
    assert len(users) == 3


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_lcl_pool_evidence_comment_users_by_auditor(
    graphql_audit_client: Client,
    graphql_audit_user: User,
    auditor_user_in_audit_team: Auditor,
    auditor_user: User,
    laika_super_admin: User,
    laika_admin_user: User,
    audit: Audit,
):
    graphql_audit_user.role = AUDITOR
    graphql_audit_user.save()

    graphql_auditor = Auditor.objects.get(user__id=graphql_audit_user.id)
    AuditorAuditFirm.objects.create(
        auditor=graphql_auditor, audit_firm=audit.audit_firm
    )
    AuditAuditor.objects.create(auditor=graphql_auditor, audit=audit)

    auditor_user_in_audit_team.role = ROLE_SUPER_ADMIN
    auditor_user_in_audit_team.save()

    response_users_lcl_pool = graphql_audit_client.execute(
        GET_AUDITOR_EVIDENCE_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': EvidenceCommentPoolsEnum.LCL.name},
    )

    users = response_users_lcl_pool['data']['auditorEvidenceCommentUsers']
    assert len(users) == 2

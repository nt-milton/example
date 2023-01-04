import tempfile

import pytest
from django.core.files import File
from graphene.test import Client

from alert.constants import ALERT_TYPES
from audit.models import Audit, AuditAlert, AuditFirm, AuditStatus
from audit.tests.factory import create_audit
from organization.models import Organization
from user.constants import ROLE_ADMIN, ROLE_SUPER_ADMIN

from .mutations import APPROVE_AUDITEE_DRAFT_REPORT
from .queries import GET_AUDITEE_ALERTS, GET_DRAFT_REPORT


@pytest.fixture
def audit_without_draft_report(audit) -> Audit:
    AuditStatus.objects.create(
        audit=audit,
        requested=True,
        initiated=True,
        fieldwork=True,
        in_draft_report=True,
    )
    return audit


@pytest.fixture
def audit_with_draft_report(
    graphql_organization: Organization, graphql_audit_firm: AuditFirm
) -> Audit:
    audit = create_audit(
        organization=graphql_organization,
        name='Laika Dev Soc 2 Type 1 Audit 2021',
        audit_firm=graphql_audit_firm,
    )
    AuditStatus.objects.create(
        audit=audit,
        requested=True,
        initiated=True,
        fieldwork=True,
        in_draft_report=True,
        draft_report=File(file=tempfile.TemporaryFile(), name='some_file_name.pdf'),
    )
    return audit


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_draft_report_not_found(
    graphql_client: Client,
    audit_without_draft_report: Audit,
):
    response = graphql_client.execute(
        GET_DRAFT_REPORT, variables={'auditId': audit_without_draft_report.id}
    )

    assert response['errors'][0]['message'] == "Uploaded Draft Report file not found"


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_draft_report(
    graphql_client: Client,
    audit_with_draft_report: Audit,
):
    response = graphql_client.execute(
        GET_DRAFT_REPORT, variables={'auditId': audit_with_draft_report.id}
    )

    assert 'some_file_name.pdf' in response['data']['auditeeAuditDraftReport']['name']


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_approve_auditee_draft_report_with_admin(
    graphql_client, graphql_user, audit, audit_status
):
    graphql_user.role = ROLE_ADMIN
    graphql_user.save()

    response = graphql_client.execute(
        APPROVE_AUDITEE_DRAFT_REPORT, variables={'input': dict(auditId=audit.id)}
    )

    assert str(
        response['data']['approveAuditeeDraftReport']['auditStatus']['id']
    ) == str(audit_status.id)


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_approve_auditee_draft_report_with_no_admin(
    graphql_client, graphql_user, audit, audit_status
):
    graphql_user.role = ROLE_SUPER_ADMIN
    graphql_user.save()

    response = graphql_client.execute(
        APPROVE_AUDITEE_DRAFT_REPORT, variables={'input': dict(auditId=audit.id)}
    )

    assert response['data']['approveAuditeeDraftReport'] is None
    assert response['errors'] is not None


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_approve_auditee_draft_report_alert(
    graphql_client, graphql_user, audit, audit_status, auditor_user, audit_auditor
):
    graphql_user.role = ROLE_ADMIN
    graphql_user.save()

    graphql_client.execute(
        APPROVE_AUDITEE_DRAFT_REPORT, variables={'input': dict(auditId=audit.id)}
    )

    audit_alert = AuditAlert.objects.all()
    assert len(audit_alert) == 1


@pytest.mark.functional(permissions=['alert.view_alert'])
def test_get_draft_report_alerts(
    graphql_client,
    graphql_user,
    audit,
    audit_status,
    auditor_user,
):
    graphql_user.role = ROLE_ADMIN
    graphql_user.save()

    AuditAlert.objects.custom_create(
        audit=audit,
        sender=auditor_user.user,
        receiver=graphql_user,
        alert_type=ALERT_TYPES['AUDITOR_PUBLISHED_DRAFT_REPORT'],
    )

    response = graphql_client.execute(
        GET_AUDITEE_ALERTS, variables={'input': dict(auditId=audit.id)}
    )

    alerts = response['data']['alerts']['data']
    assert len(alerts) == 1

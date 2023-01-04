import tempfile

import pytest
from django.core.files import File

from audit.constants import LEAD_AUDITOR_KEY, REVIEWER_AUDITOR_KEY
from audit.models import Audit, AuditAuditor, AuditStatus, DraftReportComment
from audit.tests.factory import create_audit
from auditee.tasks import digest_draft_report_new_suggestions
from user.constants import AUDITOR
from user.tests import create_user_auditor


@pytest.fixture
def audit_with_draft_report(graphql_organization, graphql_audit_firm) -> Audit:
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


@pytest.fixture
def draft_report_comment(graphql_user, audit_with_draft_report, comment):
    return DraftReportComment.objects.create(
        audit=audit_with_draft_report, comment=comment, page=2
    )


@pytest.fixture
def draft_report_resolved_comment(
    graphql_user, audit_with_draft_report, resolved_comment
):
    return DraftReportComment.objects.create(
        audit=audit_with_draft_report, comment=resolved_comment, page=2
    )


@pytest.fixture
def auditor_user2(graphql_audit_firm):
    return create_user_auditor(
        email='mattdoe@heylaika.com',
        role=AUDITOR,
        with_audit_firm=True,
        audit_firm=graphql_audit_firm.name,
    )


@pytest.mark.functional
def test_send_digest_draft_report_new_suggestions_when_new_comments(
    audit_with_draft_report, draft_report_comment, auditor_user, auditor_user2
):
    AuditAuditor.objects.create(
        audit=audit_with_draft_report, auditor=auditor_user, title_role=LEAD_AUDITOR_KEY
    )
    AuditAuditor.objects.create(
        audit=audit_with_draft_report,
        auditor=auditor_user2,
        title_role=REVIEWER_AUDITOR_KEY,
    )

    result = digest_draft_report_new_suggestions.delay().get()
    assert len(result['audits']) == 1
    assert result['success'] is True


@pytest.mark.functional
def test_send_digest_draft_report_new_suggestions_when_any_comments(
    audit_with_draft_report, auditor_user, auditor_user2
):
    AuditAuditor.objects.create(
        audit=audit_with_draft_report, auditor=auditor_user, title_role=LEAD_AUDITOR_KEY
    )
    AuditAuditor.objects.create(
        audit=audit_with_draft_report,
        auditor=auditor_user2,
        title_role=REVIEWER_AUDITOR_KEY,
    )

    result = digest_draft_report_new_suggestions.delay().get()
    assert len(result['audits']) == 0
    assert result['success'] is True


@pytest.mark.functional
def test_send_digest_draft_report_new_suggestions_when_resolved_comments(
    audit_with_draft_report, draft_report_resolved_comment, auditor_user, auditor_user2
):
    AuditAuditor.objects.create(
        audit=audit_with_draft_report, auditor=auditor_user, title_role=LEAD_AUDITOR_KEY
    )
    AuditAuditor.objects.create(
        audit=audit_with_draft_report,
        auditor=auditor_user2,
        title_role=REVIEWER_AUDITOR_KEY,
    )

    result = digest_draft_report_new_suggestions.delay().get()
    assert len(result['audits']) == 0
    assert result['success'] is True

import io
import tempfile
from datetime import datetime
from unittest.mock import patch

import pytest
from django.core.files import File
from graphene.test import Client

from alert.constants import ALERT_TYPES
from audit.constants import AUDIT_FIRMS, IN_APP_DRAFT_REPORTING_FEATURE_FLAG, SECTION_1
from audit.models import (
    Audit,
    AuditAlert,
    AuditAuditor,
    AuditFirm,
    Auditor,
    AuditorAuditFirm,
    AuditReportSection,
    AuditStatus,
)
from audit.tests.factory import create_audit, create_audit_firm
from audit.tests.fixtures.audits import SECTION_1_CONTENT
from audit.tests.queries import GET_AUDITOR_DRAFT_REPORT_SECTION_CONTENT
from auditor.report.constants import DRAFT_REPORT_VERSION, FINAL_REPORT_VERSION
from auditor.report.utils import publish_report
from feature.models import Flag
from laika.utils.dates import YYYY_MM_DD
from organization.models import Organization
from user.constants import AUDITOR
from user.models import User

from .mutations import (
    PUBLISH_AUDITOR_REPORT_VERSION,
    UPDATE_AUDITOR_AUDIT_DRAFT_REPORT,
    UPDATE_AUDITOR_AUDIT_DRAFT_REPORT_FILE,
    UPDATE_AUDITOR_DRAFT_REPORT_SECTION_CONTENT,
)
from .queries import GET_AUDITOR_ALERTS, GET_DRAFT_REPORT, GET_DRAFT_REPORT_FILE

DRAFT_REPORT_CONTENT = "This is the draft report content"
DRAFT_REPORT_NEW_CONTENT = "This is the draft report new content"


@pytest.fixture
def laika_audit_firm() -> AuditFirm:
    return create_audit_firm(AUDIT_FIRMS[0])


@pytest.fixture
def audit(graphql_organization: Organization, laika_audit_firm: AuditFirm) -> Audit:
    return create_audit(
        organization=graphql_organization,
        name='Laika Dev Soc 2 Type 1 Audit 2021',
        audit_firm=laika_audit_firm,
    )


@pytest.fixture
def requested_audit(
    graphql_organization: Organization,
    graphql_audit_user: User,
    graphql_audit_firm: AuditFirm,
) -> Audit:
    requested = create_audit(
        organization=graphql_organization,
        name='Laika Dev Soc 2 Type 1 Audit 2021 - Requested',
        audit_firm=graphql_audit_firm,
    )
    AuditStatus.objects.create(audit=requested, initiated=False)

    AuditAuditor.objects.create(audit=requested, auditor=graphql_audit_user.auditor)

    return requested


@pytest.fixture
def initiated_audit(
    graphql_organization: Organization,
    graphql_audit_user: User,
    graphql_audit_firm: AuditFirm,
) -> Audit:
    initiated = create_audit(
        organization=graphql_organization,
        name='Laika Dev Soc 2 Type 1 Audit 2021 - Initiated',
        audit_firm=graphql_audit_firm,
    )
    AuditStatus.objects.create(audit=initiated, initiated=True)
    AuditAuditor.objects.create(audit=initiated, auditor=graphql_audit_user.auditor)

    return initiated


@pytest.fixture
def fieldwork_audit_without_report(
    graphql_organization: Organization,
    graphql_audit_user: User,
    graphql_audit_firm: AuditFirm,
) -> Audit:
    fieldwork = create_audit(
        organization=graphql_organization,
        name='Laika Dev Soc 2 Type 1 Audit 2021 - Fieldwork',
        audit_firm=graphql_audit_firm,
    )
    fieldwork.audit_configuration = {
        'as_of_date': '2022-01-05',
        'trust_services_categories': ["Security"],
    }
    fieldwork.save()

    AuditStatus.objects.create(
        audit=fieldwork, requested=True, initiated=True, fieldwork=True
    )
    AuditAuditor.objects.create(audit=fieldwork, auditor=graphql_audit_user.auditor)

    return fieldwork


@pytest.fixture
def fieldwork_audit_with_report(
    graphql_organization: Organization, fieldwork_audit_without_report: Audit
) -> Audit:
    organization_name = graphql_organization.name
    audit_name = fieldwork_audit_without_report.name
    new_content_file = File(
        name=f'{organization_name}_{audit_name}_report.html',
        file=io.BytesIO(DRAFT_REPORT_CONTENT.encode()),
    )
    audit_status = fieldwork_audit_without_report.status.first()
    audit_status.draft_report_file_generated = new_content_file
    audit_status.save()

    return fieldwork_audit_without_report


@pytest.fixture
def audit_with_draft_report_not_in_firm(
    graphql_organization: Organization, laika_audit_firm: AuditFirm
) -> Audit:
    audit = create_audit(
        organization=graphql_organization,
        name='Laika Dev Soc 2 Type 1 Audit 2021',
        audit_firm=laika_audit_firm,
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
def audit_without_draft_report(
    graphql_organization: Organization,
    graphql_audit_user: User,
    graphql_audit_firm: AuditFirm,
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
    )
    AuditAuditor.objects.create(audit=audit, auditor=graphql_audit_user.auditor)
    AuditorAuditFirm.objects.create(
        auditor=graphql_audit_user.auditor, audit_firm=graphql_audit_firm
    )
    return audit


@pytest.fixture
def audit_with_draft_report(
    graphql_organization: Organization,
    graphql_audit_user: User,
    laika_audit_firm: AuditFirm,
) -> Audit:
    audit = create_audit(
        organization=graphql_organization,
        name='Laika Dev Soc 2 Type 1 Audit 2021',
        audit_firm=laika_audit_firm,
    )
    AuditStatus.objects.create(
        audit=audit,
        requested=True,
        initiated=True,
        fieldwork=True,
        in_draft_report=True,
        draft_report=File(file=tempfile.TemporaryFile(), name='some_file_name.pdf'),
    )
    auditor = Auditor(user=graphql_audit_user)
    auditor.save(is_not_django=True)
    AuditAuditor.objects.create(audit=audit, auditor=auditor)
    AuditorAuditFirm.objects.create(auditor=auditor, audit_firm=laika_audit_firm)
    return audit


@pytest.fixture
def auditor_for_audit_without_draft_report(
    graphql_organization: Organization,
    graphql_audit_user: User,
    laika_audit_firm: AuditFirm,
) -> Audit:
    audit = create_audit(
        organization=graphql_organization,
        name='Laika Dev Soc 2 Type 1 Audit 2021',
        audit_firm=laika_audit_firm,
    )
    AuditStatus.objects.create(
        audit=audit,
        requested=True,
        initiated=True,
        fieldwork=True,
        in_draft_report=True,
    )
    auditor = Auditor(user=graphql_audit_user)
    auditor.save(is_not_django=True)
    AuditAuditor.objects.create(audit=audit, auditor=auditor)
    AuditorAuditFirm.objects.create(auditor=auditor, audit_firm=laika_audit_firm)
    return audit


@pytest.fixture()
def in_app_draft_reporting_flag(graphql_organization):
    Flag.objects.get_or_create(
        name=IN_APP_DRAFT_REPORTING_FEATURE_FLAG,
        organization=graphql_organization,
        is_enabled=True,
    )


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_draft_report_file_audit_not_found(
    graphql_audit_client: Client,
):
    response = graphql_audit_client.execute(
        GET_DRAFT_REPORT_FILE, variables={'auditId': 123}
    )

    assert 'Not found' in response['errors'][0]['message']


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_draft_report_file_auditor_not_in_firm(
    graphql_audit_client: Client,
    audit: Audit,
):
    response = graphql_audit_client.execute(
        GET_DRAFT_REPORT_FILE, variables={'auditId': audit.id}
    )

    assert response['errors'][0]['message'] == "Auditor can not get draft report file"


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_draft_report_file_not_in_stage_requested(
    graphql_audit_client: Client,
    requested_audit: Audit,
):
    response = graphql_audit_client.execute(
        GET_DRAFT_REPORT_FILE, variables={'auditId': requested_audit.id}
    )

    assert (
        response['errors'][0]['message']
        == "Invalid audit stage to return a draft report file"
    )


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_draft_report_file_not_in_stage_initiated(
    graphql_audit_client: Client,
    initiated_audit: Audit,
):
    response = graphql_audit_client.execute(
        GET_DRAFT_REPORT_FILE, variables={'auditId': initiated_audit.id}
    )

    assert (
        response['errors'][0]['message']
        == "Invalid audit stage to return a draft report file"
    )


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_draft_report_file_not_generated(
    graphql_audit_client: Client,
    fieldwork_audit_without_report: Audit,
):
    response = graphql_audit_client.execute(
        GET_DRAFT_REPORT_FILE, variables={'auditId': fieldwork_audit_without_report.id}
    )

    assert (
        response['errors'][0]['message']
        == "Audit draft report file hasn't been generated yet"
    )


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_draft_report_file(
    graphql_audit_client: Client,
    fieldwork_audit_with_report: Audit,
):
    response = graphql_audit_client.execute(
        GET_DRAFT_REPORT_FILE, variables={'auditId': fieldwork_audit_with_report.id}
    )

    audit_status = fieldwork_audit_with_report.status.first()

    assert audit_status.draft_report_file_generated is not None
    assert (
        response['data']['auditorAuditDraftReportFile']['content']
        == DRAFT_REPORT_CONTENT
    )


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_update_draft_report_audit_not_found(graphql_audit_client: Client):
    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_AUDIT_DRAFT_REPORT_FILE,
        variables={'input': dict(auditId=123, content=DRAFT_REPORT_NEW_CONTENT)},
    )

    assert 'Not found' in response['errors'][0]['message']


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_update_draft_report_not_in_firm(
    graphql_audit_client: Client,
    audit: Audit,
):
    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_AUDIT_DRAFT_REPORT_FILE,
        variables={'input': dict(auditId=audit.id, content=DRAFT_REPORT_NEW_CONTENT)},
    )

    assert (
        response['errors'][0]['message'] == "Auditor can not update draft report file"
    )


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_update_draft_report_not_in_stage_requested(
    graphql_audit_client: Client,
    requested_audit: Audit,
):
    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_AUDIT_DRAFT_REPORT_FILE,
        variables={
            'input': dict(auditId=requested_audit.id, content=DRAFT_REPORT_NEW_CONTENT)
        },
    )

    assert (
        response['errors'][0]['message']
        == "Invalid audit stage to return a draft report file"
    )


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_update_draft_report_not_in_stage_initiated(
    graphql_audit_client: Client,
    initiated_audit: Audit,
):
    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_AUDIT_DRAFT_REPORT_FILE,
        variables={
            'input': dict(auditId=initiated_audit.id, content=DRAFT_REPORT_NEW_CONTENT)
        },
    )

    assert (
        response['errors'][0]['message']
        == "Invalid audit stage to return a draft report file"
    )


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_update_draft_report_not_generated(
    graphql_audit_client: Client,
    fieldwork_audit_without_report: Audit,
):
    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_AUDIT_DRAFT_REPORT_FILE,
        variables={
            'input': dict(
                auditId=fieldwork_audit_without_report.id,
                content=DRAFT_REPORT_NEW_CONTENT,
            )
        },
    )

    assert (
        response['errors'][0]['message']
        == "Audit draft report file hasn't been generated yet"
    )


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_update_draft_report(
    graphql_audit_client: Client,
    fieldwork_audit_with_report: Audit,
):
    graphql_audit_client.execute(
        UPDATE_AUDITOR_AUDIT_DRAFT_REPORT_FILE,
        variables={
            'input': dict(
                auditId=fieldwork_audit_with_report.id, content=DRAFT_REPORT_NEW_CONTENT
            )
        },
    )

    audit_status = fieldwork_audit_with_report.status.first()
    audit_draft_report = audit_status.draft_report_file_generated
    draft_report_content = audit_draft_report.file.read().decode('UTF-8')

    assert draft_report_content == DRAFT_REPORT_NEW_CONTENT


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_draft_report_not_in_firm(
    graphql_audit_client: Client, audit_with_draft_report_not_in_firm: Audit
):
    response = graphql_audit_client.execute(
        GET_DRAFT_REPORT, variables={'auditId': audit_with_draft_report_not_in_firm.id}
    )

    assert response['errors'][0]['message'] == "Auditor can not get draft report"


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_draft_report_not_found(
    graphql_audit_client: Client, audit_without_draft_report: Audit
):
    response = graphql_audit_client.execute(
        GET_DRAFT_REPORT, variables={'auditId': audit_without_draft_report.id}
    )

    assert response['errors'][0]['message'] == "Uploaded Draft Report file not found"


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_draft_report(graphql_audit_client: Client, audit_with_draft_report: Audit):
    response = graphql_audit_client.execute(
        GET_DRAFT_REPORT, variables={'auditId': audit_with_draft_report.id}
    )

    assert 'some_file_name.pdf' in response['data']['auditorAuditDraftReport']['name']


@pytest.mark.functional(permissions=['audit.view_auditalert'])
def test_get_draft_report_alerts(
    graphql_audit_client: Client,
    audit: Audit,
    graphql_audit_user: User,
    laika_super_admin: User,
):
    graphql_audit_user.role = AUDITOR
    graphql_audit_user.save()
    AuditAlert.objects.custom_create(
        audit=audit,
        sender=laika_super_admin,
        receiver=graphql_audit_user,
        alert_type=ALERT_TYPES['ORG_APPROVED_DRAFT_REPORT'],
    )

    AuditAlert.objects.custom_create(
        audit=audit,
        sender=laika_super_admin,
        receiver=graphql_audit_user,
        alert_type=ALERT_TYPES['ORG_SUGGESTED_DRAFT_EDITS'],
    )
    response = graphql_audit_client.execute(
        GET_AUDITOR_ALERTS, variables={'auditId': audit.id}
    )

    alerts = response['data']['auditorAlerts']['alerts']
    assert len(alerts) == 2


@pytest.mark.functional(permissions=['audit.publish_draft_report'])
def test_update_audit_auditor_draft_report_not_in_firm(
    graphql_audit_client: Client,
    audit: Audit,
):
    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_AUDIT_DRAFT_REPORT, variables={'input': dict(auditId=audit.id)}
    )
    assert response['errors'][0]['message'] == "Auditor can not publish draft report"


@pytest.mark.functional(permissions=['audit.publish_draft_report'])
def test_update_audit_auditor_draft_report_not_generated(
    graphql_audit_client: Client,
    fieldwork_audit_without_report: Audit,
):
    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_AUDIT_DRAFT_REPORT,
        variables={'input': dict(auditId=fieldwork_audit_without_report.id)},
    )
    assert (
        response['errors'][0]['message']
        == "Audit draft report file hasn't been generated yet"
    )


@pytest.mark.functional(permissions=['audit.publish_draft_report'])
def test_update_audit_auditor_draft_report_not_in_stage_requested(
    graphql_audit_client: Client,
    requested_audit: Audit,
):
    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_AUDIT_DRAFT_REPORT,
        variables={'input': dict(auditId=requested_audit.id)},
    )

    assert (
        response['errors'][0]['message']
        == "Invalid audit stage to return a draft report file"
    )


@pytest.mark.functional(permissions=['audit.publish_draft_report'])
def test_update_audit_auditor_draft_report(
    graphql_audit_client: Client,
    fieldwork_audit_with_report: Audit,
):
    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_AUDIT_DRAFT_REPORT,
        variables={'input': dict(auditId=fieldwork_audit_with_report.id)},
    )

    audit_status = fieldwork_audit_with_report.status.first()

    assert audit_status.draft_report is not None
    assert 'Draft_' in (
        response['data']['updateAuditorAuditDraftReport']['audit']['draftReport'][
            'name'
        ]
    )


@pytest.mark.functional(permissions=['audit.publish_draft_report'])
def test_update_audit_auditor_draft_report_alert(
    graphql_audit_client: Client,
    fieldwork_audit_with_report: Audit,
    graphql_audit_user: User,
    laika_admin_user: User,
    in_app_draft_reporting_flag,
):
    graphql_audit_client.execute(
        UPDATE_AUDITOR_AUDIT_DRAFT_REPORT,
        variables={'input': dict(auditId=fieldwork_audit_with_report.id)},
    )

    alert = AuditAlert.objects.all()
    assert len(alert) == 1


@pytest.mark.functional(permissions=['audit.publish_draft_report'])
@patch('laika.aws.ses.ses.send_email')
def test_publish_draft_report_email_enabled_flag(
    send_email,
    graphql_audit_client: Client,
    fieldwork_audit_with_report: Audit,
    graphql_audit_user: User,
    laika_admin_user: User,
    in_app_draft_reporting_flag,
):
    graphql_audit_client.execute(
        UPDATE_AUDITOR_AUDIT_DRAFT_REPORT,
        variables={'input': dict(auditId=fieldwork_audit_with_report.id)},
    )
    send_email.assert_called_once()


@pytest.mark.functional(permissions=['audit.publish_draft_report'])
@patch('laika.aws.ses.ses.send_email')
def test_publish_draft_report_email_no_flag(
    send_email,
    graphql_audit_client: Client,
    fieldwork_audit_with_report: Audit,
    graphql_audit_user: User,
    laika_admin_user: User,
):
    graphql_audit_client.execute(
        UPDATE_AUDITOR_AUDIT_DRAFT_REPORT,
        variables={'input': dict(auditId=fieldwork_audit_with_report.id)},
    )
    send_email.assert_not_called()


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_draft_report_section_content(
    graphql_audit_client, audit_soc2_type2_with_section
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_DRAFT_REPORT_SECTION_CONTENT,
        variables={
            'auditId': audit_soc2_type2_with_section.id,
            'section': SECTION_1,
        },
    )
    assert (
        response['data']['auditorDraftReportSectionContent']['sectionContent']
        == SECTION_1_CONTENT
    )


@pytest.mark.functional(permissions=['audit.update_draft_report'])
def test_update_draft_report_section_content(
    graphql_audit_client, audit_soc2_type2_with_section
):
    new_content = 'Test content updated'
    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_DRAFT_REPORT_SECTION_CONTENT,
        variables={
            'input': {
                'auditId': audit_soc2_type2_with_section.id,
                'section': SECTION_1,
                'content': new_content,
            }
        },
    )
    section = AuditReportSection.objects.get(id=audit_soc2_type2_with_section.id)

    assert section.file.read().decode('UTF-8') == new_content
    assert (
        response['data']['updateAuditorDraftReportSectionContent']['name']
        == 'Section I: This is a test'
    )


@pytest.mark.functional(permissions=['audit.publish_draft_report'])
def test_update_draft_report_section_content_with_wrong_permissions(
    graphql_audit_client, audit_soc2_type2_with_section, caplog
):
    new_content = 'Test content updated'
    graphql_audit_client.execute(
        UPDATE_AUDITOR_DRAFT_REPORT_SECTION_CONTENT,
        variables={
            'input': {
                'auditId': audit_soc2_type2_with_section.id,
                'section': SECTION_1,
                'content': new_content,
            }
        },
    )
    for log_output in [
        "Failed to update draft report section content",
        "PermissionDenied",
        "operation: UpdateAuditorDraftReportSectionContent.mutate",
    ]:
        assert log_output in caplog.text


@pytest.mark.functional(permissions=['audit.publish_draft_report'])
def test_publish_draft_report_version(
    graphql_audit_client, audit_soc2_type2_with_section
):
    response = graphql_audit_client.execute(
        PUBLISH_AUDITOR_REPORT_VERSION,
        variables={
            'input': {
                'auditId': audit_soc2_type2_with_section.id,
                'version': DRAFT_REPORT_VERSION,
            }
        },
    )

    assert response['data']['publishAuditorReportVersion']['success'] is True


@pytest.mark.functional(permissions=['audit.publish_draft_report'])
def test_publish_final_report_version(
    graphql_audit_client, audit_soc2_type2_with_section
):
    response = graphql_audit_client.execute(
        PUBLISH_AUDITOR_REPORT_VERSION,
        variables={
            'input': {
                'auditId': audit_soc2_type2_with_section.id,
                'version': FINAL_REPORT_VERSION,
                'reportPublishDate': '2022-11-14',
            }
        },
    )
    assert response['data']['publishAuditorReportVersion']['success'] is True


@pytest.mark.functional
@patch('laika.aws.ses.ses.send_email')
def test_publish_report_draft_version_email_enabled_flag(
    send_email,
    graphql_audit_client: Client,
    audit_soc2_type2_with_section: Audit,
    graphql_audit_user: User,
    laika_admin_user: User,
    in_app_draft_reporting_flag,
):
    publish_report(
        audit_soc2_type2_with_section, DRAFT_REPORT_VERSION, graphql_audit_user
    )
    assert list(audit_soc2_type2_with_section.status.all())[0].draft_report is not None
    send_email.assert_called_once()


@pytest.mark.functional
@patch('laika.aws.ses.ses.send_email')
def test_publish_report_draft_version_email_no_flag(
    send_email,
    graphql_audit_client: Client,
    audit_soc2_type2_with_section: Audit,
    graphql_audit_user: User,
    laika_admin_user: User,
):
    publish_report(
        audit_soc2_type2_with_section, DRAFT_REPORT_VERSION, graphql_audit_user
    )
    assert list(audit_soc2_type2_with_section.status.all())[0].draft_report is not None
    send_email.assert_not_called()


@pytest.mark.functional
@patch('laika.aws.ses.ses.send_email')
def test_publish_report_final_version(
    send_email,
    audit_soc2_type2_with_section: Audit,
    graphql_audit_user: User,
    laika_admin_user: User,
):
    publish_report(
        audit_soc2_type2_with_section, FINAL_REPORT_VERSION, graphql_audit_user
    )
    today = datetime.now().strftime(YYYY_MM_DD)
    audit_status = list(audit_soc2_type2_with_section.status.all())[0]
    assert audit_status.final_report is not None
    assert audit_status.completed is True
    assert audit_soc2_type2_with_section.completed_at.strftime(YYYY_MM_DD) == today
    send_email.assert_called_once()

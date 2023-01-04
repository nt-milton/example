from unittest.mock import patch

import pytest
from django.test import Client

from audit.constants import SECTION_1
from audit.models import Audit, AuditReportSection
from auditor.tests.mutations import UPDATE_AUDITOR_AUDIT_REPORT_SECTION
from fieldwork.models import Requirement


@pytest.fixture
def audit_report_section(audit_soc2_type2):
    return AuditReportSection.objects.create(
        name='Test audit report section', audit=audit_soc2_type2, section=SECTION_1
    )


@pytest.mark.functional(permissions=['audit.update_draft_report'])
@patch(
    'audit.sections_factory.SOC2_Type2_sections_factory.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
def test_refresh_audit_section(
    get_requirements_by_args_mock,
    graphql_audit_client: Client,
    audit_soc2_type2: Audit,
    audit_report_section: AuditReportSection,
):
    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_AUDIT_REPORT_SECTION,
        variables={'input': {'auditId': audit_soc2_type2.id, 'section': SECTION_1}},
    )
    assert response['data']['updateAuditorAuditReportSection']['audit'] is not None


@pytest.mark.functional(permissions=['audit.publish_draft_report'])
def test_refresh_audit_section_with_wrong_permissions(
    graphql_audit_client: Client,
    audit_soc2_type2: Audit,
    audit_report_section: AuditReportSection,
    caplog,
):
    graphql_audit_client.execute(
        UPDATE_AUDITOR_AUDIT_REPORT_SECTION,
        variables={'input': {'auditId': audit_soc2_type2.id, 'section': SECTION_1}},
    )
    for log_output in [
        "Failed to refresh audit section",
        "PermissionDenied",
        "operation: UpdateAuditorAuditReportSection.mutate",
    ]:
        assert log_output in caplog.text

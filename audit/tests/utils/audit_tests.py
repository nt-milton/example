import tempfile

import pytest
from django.core.files import File

from audit.constants import CURRENT_AUDIT_STATUS
from audit.models import Audit, AuditStatus
from audit.tests.constants import SOC_2_TYPE_1
from audit.tests.factory import (
    associate_organization_audit_firm,
    create_audit,
    create_coupon,
    get_framework_type_from_key,
)
from audit.utils.audit import get_current_status, get_report_file

AUDIT_NAME = 'Laika Dev Soc 2 Type 1 Audit 2021'


@pytest.fixture
def soc2_type1_coupon(graphql_organization, graphql_audit_firm):
    framework_type = get_framework_type_from_key(SOC_2_TYPE_1)
    return create_coupon(
        graphql_organization,
        coupon_type=f'{framework_type} {graphql_audit_firm.name}',
        coupon_count=6,
    )


@pytest.fixture
def audit_in_progress(graphql_organization, graphql_audit_firm, soc2_type1_coupon):
    associate_organization_audit_firm(graphql_organization, graphql_audit_firm)

    audit_1 = create_audit(
        organization=graphql_organization,
        name=AUDIT_NAME,
        audit_firm=graphql_audit_firm,
    )

    audit_2 = create_audit(
        organization=graphql_organization,
        name=AUDIT_NAME,
        audit_firm=graphql_audit_firm,
    )
    AuditStatus.objects.create(audit=audit_1, requested=True)
    AuditStatus.objects.create(
        audit=audit_2,
        requested=True,
        initiated=True,
        fieldwork=True,
        in_draft_report=True,
        draft_report=File(file=tempfile.TemporaryFile(), name='some_file_name.pdf'),
    )


@pytest.mark.functional
def test_get_current_status(audit_in_progress):
    [audit_status_requested, audit_status_draft_report] = AuditStatus.objects.all()

    current_status_requested = get_current_status(audit_status_requested)
    current_status_draft_report = get_current_status(audit_status_draft_report)

    assert current_status_requested == CURRENT_AUDIT_STATUS['REQUESTED']
    assert current_status_draft_report == CURRENT_AUDIT_STATUS['IN_DRAFT_REPORT']


@pytest.mark.functional
def test_get_report_file(audit_in_progress):
    audit = Audit.objects.last()

    report_file = get_report_file(
        audit=audit,
        current_status=CURRENT_AUDIT_STATUS['IN_DRAFT_REPORT'],
        report_field='draft_report',
    )
    assert report_file is not None

    report_file = get_report_file(
        audit=audit,
        current_status=CURRENT_AUDIT_STATUS['IN_DRAFT_REPORT'],
        report_field='final_report',
    )
    assert not bool(report_file)

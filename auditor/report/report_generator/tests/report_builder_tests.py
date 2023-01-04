from datetime import datetime

import pytest

from audit.constants import SECTION_1, SECTION_5
from audit.models import AuditFirm
from audit.tests.fixtures.audits import SECTION_1_CONTENT
from auditor.report.report_generator.report_builder import (
    PORTRAIT_ORIENTATION,
    ReportBuilder,
)
from auditor.report.report_generator.report_director import LANDSCAPE_ORIENTATION


@pytest.fixture
def report_builder_for_soc2_type2(audit_soc2_type2_with_section):
    return ReportBuilder(audit=audit_soc2_type2_with_section)


@pytest.mark.functional
def test_create_header_and_footer_files_landscape_orientation(
    report_builder_for_soc2_type2: ReportBuilder,
):
    report_builder_for_soc2_type2._create_header_and_footer_files(
        SECTION_1, LANDSCAPE_ORIENTATION
    )
    assert (
        report_builder_for_soc2_type2.header_and_footer_current_orientation
        == LANDSCAPE_ORIENTATION
    )


@pytest.mark.functional
def test_create_header_and_footer_files_portrait_orientation(
    report_builder_for_soc2_type2: ReportBuilder,
):
    report_builder_for_soc2_type2._create_header_and_footer_files(
        SECTION_1, PORTRAIT_ORIENTATION
    )
    assert (
        report_builder_for_soc2_type2.header_and_footer_current_orientation
        == PORTRAIT_ORIENTATION
    )


@pytest.mark.functional
def test_get_unexisting_report_section(report_builder_for_soc2_type2: ReportBuilder):
    report_builder_for_soc2_type2.audit.report_sections.get(section=SECTION_5).delete()
    assert report_builder_for_soc2_type2._get_report_section(SECTION_5) is None


@pytest.mark.functional
def test_get_existing_report_section(report_builder_for_soc2_type2: ReportBuilder):
    assert report_builder_for_soc2_type2._get_report_section(SECTION_1) is not None


@pytest.mark.functional
def test_separate_section_1(report_builder_for_soc2_type2: ReportBuilder):
    cover, section = report_builder_for_soc2_type2._separate_section_1(
        SECTION_1_CONTENT
    )
    assert cover is not None
    assert section is not None


@pytest.mark.functional
def test_signature_html(
    report_builder_for_soc2_type2: ReportBuilder, graphql_audit_firm: AuditFirm
):
    graphql_audit_firm.signature_text = 'Laika Compliance LLC'
    graphql_audit_firm.save()
    signature_html = report_builder_for_soc2_type2._get_signature_html()
    assert (
        report_builder_for_soc2_type2.audit.audit_firm.signature_text in signature_html
    )


@pytest.mark.functional
def test_report_final_date(report_builder_for_soc2_type2: ReportBuilder):
    audit_status = report_builder_for_soc2_type2.audit.status.first()
    audit_status.final_report_updated_at = datetime.strptime('2022-11-14', '%Y-%m-%d')
    audit_status.save()

    publish_date = report_builder_for_soc2_type2._get_formatted_publish_date()

    assert 'November 14, 2022' == publish_date

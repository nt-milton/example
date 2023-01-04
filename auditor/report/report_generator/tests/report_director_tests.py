import pytest

from audit.constants import SECTION_1, SECTION_2, SECTION_4
from auditor.report.report_generator.report_director import ReportDirector
from fieldwork.models import Requirement, Test


@pytest.fixture
def report_director_for_soc2_type2(audit_soc2_type2_with_section):
    return ReportDirector(audit=audit_soc2_type2_with_section)


@pytest.fixture
def requirement_with_exceptions_noted_test(audit_soc2_type2_with_section):
    new_requirement = Requirement.objects.create(
        audit=audit_soc2_type2_with_section, display_id='LCL-10', name='LCL-10'
    )
    Test.objects.create(
        display_id='TEST-1',
        name='TEST-1',
        result='exceptions_noted',
        requirement=new_requirement,
    )
    return new_requirement


@pytest.mark.functional
def test_create_soc_2_draft_report_pdf_all_sections(
    report_director_for_soc2_type2: ReportDirector,
    requirement_with_exceptions_noted_test: Requirement,
):
    assert report_director_for_soc2_type2.create_soc_2_draft_report_pdf() is not None


@pytest.mark.functional
def test_create_soc_2_final_report_pdf_all_sections(
    report_director_for_soc2_type2: ReportDirector,
    requirement_with_exceptions_noted_test: Requirement,
):
    assert report_director_for_soc2_type2.create_soc_2_final_report_pdf() is not None


@pytest.mark.functional
def test_create_soc_2_draft_report_pdf_without_section_5(
    report_director_for_soc2_type2: ReportDirector,
):
    assert report_director_for_soc2_type2.create_soc_2_draft_report_pdf() is not None


@pytest.mark.functional
def test_create_soc_2_final_report_pdf_without_section_5(
    report_director_for_soc2_type2: ReportDirector,
):
    assert report_director_for_soc2_type2.create_soc_2_final_report_pdf() is not None


@pytest.mark.functional
def test_create_section_1_pdf(
    report_director_for_soc2_type2: ReportDirector,
):
    assert report_director_for_soc2_type2.create_section_pdf(SECTION_1) is not None


@pytest.mark.functional
def test_create_portrait_section_pdf(
    report_director_for_soc2_type2: ReportDirector,
):
    assert report_director_for_soc2_type2.create_section_pdf(SECTION_2) is not None


@pytest.mark.functional
def test_create_landscape_section_pdf(
    report_director_for_soc2_type2: ReportDirector,
):
    assert report_director_for_soc2_type2.create_section_pdf(SECTION_4) is not None


@pytest.mark.functional
def test_should_include_section_5_returns_false(
    report_director_for_soc2_type2: ReportDirector,
):
    assert report_director_for_soc2_type2._should_include_section_5() is False


@pytest.mark.functional
def test_should_include_section_5_returns_true(
    report_director_for_soc2_type2: ReportDirector,
    requirement_with_exceptions_noted_test: Requirement,
):
    assert report_director_for_soc2_type2._should_include_section_5() is True

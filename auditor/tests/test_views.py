import pytest
from django.http import HttpResponseBadRequest
from django.template import loader

from audit.constants import SECTION_1
from auditor.report.report_generator.report_builder import DRAFT_VERSION, FINAL_VERSION
from auditor.views import get_pdf_from_draft_report_html

JSON_CONTENT_TYPE = 'application/json'


@pytest.fixture
def draft_report_html() -> str:
    report_template = loader.get_template('SOC-report-template.html')
    report_template_html = report_template.render()
    return report_template_html


def _download_draft_report_section_pdf_call(http_client, payload):
    return http_client.post(
        path='/auditor/export-draft-report-section-pdf', data=payload
    )


def _download_report_pdf_call(http_client, payload):
    return http_client.post(path='/auditor/export-report-pdf', data=payload)


@pytest.mark.django_db
def test_get_pdf_from_draft_report_html(audit, draft_report_html):
    audit.audit_configuration = {
        'as_of_date': '2021-08-17',
        'trust_services_categories': ["Security"],
    }

    draft_report_pdf = get_pdf_from_draft_report_html(audit, draft_report_html)

    assert "This is a Test PDF stamped".encode() == draft_report_pdf.read()


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_export_draft_report_section_pdf(http_client, audit_soc2_type2_with_section):
    payload = dict(auditId=audit_soc2_type2_with_section.id, section=SECTION_1)
    response = _download_draft_report_section_pdf_call(
        http_client=http_client, payload=payload
    )
    assert response.status_code == 200
    assert response['Content-Type'] == 'application/octet-stream'


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_export_draft_report_section_pdf_without_valid_section(
    http_client, audit_soc2_type2
):
    payload = dict(auditId=audit_soc2_type2.id, section='section_X')
    response = _download_draft_report_section_pdf_call(
        http_client=http_client, payload=payload
    )
    assert response.status_code == HttpResponseBadRequest().status_code


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_export_draft_report_section_pdf_without_id(http_client, audit_soc2_type2):
    payload = dict(auditId='', section=SECTION_1)
    response = _download_draft_report_section_pdf_call(
        http_client=http_client, payload=payload
    )
    assert response.status_code == HttpResponseBadRequest().status_code


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_export_draft_report_pdf(http_client, audit_soc2_type2_with_section):
    payload = dict(auditId=audit_soc2_type2_with_section.id, version=DRAFT_VERSION)
    response = _download_report_pdf_call(http_client=http_client, payload=payload)
    assert response.status_code == 200
    assert response['Content-Type'] == 'application/octet-stream'


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_export_final_report_pdf(http_client, audit_soc2_type2_with_section):
    payload = dict(
        auditId=audit_soc2_type2_with_section.id,
        version=FINAL_VERSION,
        reportPublishDate='2022-12-22',
    )
    response = _download_report_pdf_call(http_client=http_client, payload=payload)
    assert response.status_code == 200
    assert response['Content-Type'] == 'application/octet-stream'


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_export_report_pdf_without_id(http_client, audit_soc2_type2):
    payload = dict(auditId='', version=FINAL_VERSION)
    response = _download_report_pdf_call(http_client=http_client, payload=payload)
    assert response.status_code == HttpResponseBadRequest().status_code


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_export_report_pdf_without_valid_version(
    http_client, audit_soc2_type2_with_section
):
    payload = dict(auditId=audit_soc2_type2_with_section.id, version='not_valid')
    response = _download_report_pdf_call(http_client=http_client, payload=payload)
    assert response.status_code == HttpResponseBadRequest().status_code

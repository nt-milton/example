from unittest.mock import patch

import pytest
from django.http import HttpResponseBadRequest

import evidence.constants as constants
from evidence.tests import create_evidence

APPLICATION_PDF = 'application/pdf'


def _get_content_disposition(file_name=''):
    return f'attachment;filename="{file_name}"'


@pytest.fixture
def legacy_document_evidence(graphql_organization):
    return create_evidence(graphql_organization, [constants.LEGACY_DOCUMENT]).first()


@pytest.fixture
def file_evidence(graphql_organization):
    return create_evidence(graphql_organization, [constants.FILE]).first()


@pytest.fixture
def paper_evidence(graphql_organization):
    return create_evidence(graphql_organization, [constants.LAIKA_PAPER]).first()


@pytest.fixture
def policy_evidence(graphql_organization):
    return create_evidence(graphql_organization, [constants.POLICY]).first()


def _evidence_export_call(http_client, payload):
    return http_client.post(path='/evidence/export', data=payload)


def _export_assertions(
    response, content_disposition, status_code=200, content_type=APPLICATION_PDF
):
    assert response.status_code == status_code
    assert response['Content-Disposition'] == content_disposition
    assert response['Content-Type'] == content_type


@pytest.mark.django_db
def test_export_evidence_without_id(http_client):
    response = _evidence_export_call(http_client, {'id': ''})
    assert response.status_code == HttpResponseBadRequest().status_code


@pytest.mark.django_db
def test_export_legacy_document_evidence(http_client, legacy_document_evidence):
    with patch('evidence.views.get_document_pdf') as get_document_pdf:
        response = _evidence_export_call(
            http_client, {'id': legacy_document_evidence.id}
        )
        assert get_document_pdf.called is True
    _export_assertions(
        response,
        content_disposition=_get_content_disposition('file-test-LEGACY_DOCUMENT-0.pdf'),
    )


@pytest.mark.django_db
def test_export_file_evidence(http_client, file_evidence):
    response = _evidence_export_call(http_client, {'id': file_evidence.id})
    _export_assertions(
        response,
        content_disposition=_get_content_disposition('file-test-FILE-0'),
        content_type='application/octet-stream',
    )


@pytest.mark.django_db
def test_export_paper_evidence(http_client, paper_evidence):
    with patch('pdfkit.from_string') as convert_html_text_to_pdf:
        response = _evidence_export_call(http_client, {'id': paper_evidence.id})
        convert_html_text_to_pdf.assert_called()
    _export_assertions(
        response,
        content_disposition=_get_content_disposition('file-test-LAIKA_PAPER-0.pdf'),
    )


@pytest.mark.django_db
def test_export_policy_evidence(http_client, policy_evidence):
    response = _evidence_export_call(http_client, {'id': policy_evidence.id})
    _export_assertions(
        response, content_disposition=_get_content_disposition('file-test-POLICY-0.pdf')
    )

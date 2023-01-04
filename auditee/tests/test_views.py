import os

import pytest
from django.core.files import File
from django.http import HttpResponseBadRequest

from audit.models import Audit
from laika.constants import OCTET_STREAM_CONTENT_TYPE
from laika.utils.spreadsheet import CONTENT_TYPE
from population.models import AuditPopulation, PopulationCompletenessAccuracy

JSON_CONTENT_TYPE = 'application/json'
template_seed_file_path = f'{os.path.dirname(__file__)}/resources/template_seed.xlsx'
test_pdf_file_path = f'{os.path.dirname(__file__)}/resources/test_pdf.pdf'


def _download_population_file_call(http_client, payload):
    return http_client.post(path='/population/download-population-file', data=payload)


def _download_population_template_call(http_client, payload):
    return http_client.post(path='/population/export-population-template', data=payload)


def _download_population_completeness_and_accuracy_file(http_client, payload):
    return http_client.post(
        path='/population/download-completeness-and-accuracy-file', data=payload
    )


@pytest.fixture
def audit_population_with_data_file(audit: Audit) -> AuditPopulation:
    population = AuditPopulation.objects.create(
        audit=audit,
        name='Population Name',
        instructions='Instructions test',
        description='description test',
        data_file=File(open(template_seed_file_path, "rb")),
        data_file_name='template_seed.xlsx',
    )
    return population


@pytest.fixture
def audit_population_with_completeness_and_accuracy_file(
    audit: Audit,
) -> AuditPopulation:
    population = AuditPopulation.objects.create(
        audit=audit,
        name='Population Name',
        instructions='Instructions test',
        description='description test',
    )
    PopulationCompletenessAccuracy.objects.create(
        population=population,
        name='test.pdf',
        file=File(open(test_pdf_file_path, "rb")),
    )
    return population


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_download_population_file_without_id(
    audit, audit_population_with_data_file, http_client
):
    response = _download_population_file_call(http_client, {'id': ''})
    assert response.status_code == HttpResponseBadRequest().status_code


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_download_population_file_data_file(
    http_client, audit_population_with_data_file
):
    response = _download_population_file_call(http_client, {'id': '1'})
    assert response.status_code == 200
    assert response['Content-Type'] == OCTET_STREAM_CONTENT_TYPE
    assert (
        response['Content-Disposition'] == 'attachment;filename="Population Name.xlsx"'
    )


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_download_population_template_without_display_id(
    audit, audit_population_with_data_file, http_client
):
    response = _download_population_template_call(
        http_client, {'populationDisplayId': ''}
    )
    assert response.status_code == HttpResponseBadRequest().status_code


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_download_population_file_template(
    http_client, audit_population_with_data_file
):
    response = _download_population_template_call(
        http_client, {'populationDisplayId': 'POP-1'}
    )
    assert response.status_code == 200
    assert response['Content-Type'] == CONTENT_TYPE
    assert (
        response['Content-Disposition']
        == 'attachment; filename="POP_CURRENT_EMPLOYEES_TEMPLATE.xlsx"'
    )
    assert response['Template-Filename'] == 'POP_CURRENT_EMPLOYEES_TEMPLATE.xlsx'


@pytest.mark.functional(permissions=['population.view_populationcompletenessaccuracy'])
def test_download_population_completeness_and_accuracy_file(
    http_client, audit_population_with_completeness_and_accuracy_file
):
    # fmt: off
    completeness_and_accuracy = audit_population_with_completeness_and_accuracy_file \
        .completeness_accuracy.first()
    # fmt: on
    response = _download_population_completeness_and_accuracy_file(
        http_client,
        {
            'auditId': audit_population_with_completeness_and_accuracy_file.audit.id,
            'populationId': audit_population_with_completeness_and_accuracy_file.id,
            'fileId': completeness_and_accuracy.id,
        },
    )
    assert response.status_code == 200
    assert response['Content-Type'] == OCTET_STREAM_CONTENT_TYPE
    assert (
        response['Content-Disposition']
        == f'attachment;filename="{completeness_and_accuracy.name}"'
    )


@pytest.mark.functional(permissions=['population.view_populationcompletenessaccuracy'])
def test_download_population_completeness_and_accuracy_file_without_audit_id(
    audit_population_with_completeness_and_accuracy_file, http_client
):
    # fmt: off
    completeness_and_accuracy = audit_population_with_completeness_and_accuracy_file \
        .completeness_accuracy.first()
    # fmt: on
    response = _download_population_completeness_and_accuracy_file(
        http_client,
        {
            'auditId': '',
            'populationId': audit_population_with_completeness_and_accuracy_file.id,
            'fileId': completeness_and_accuracy.id,
        },
    )
    assert response.status_code == HttpResponseBadRequest().status_code


@pytest.mark.functional(permissions=['population.view_populationcompletenessaccuracy'])
def test_download_population_completeness_and_accuracy_file_without_pop_id(
    audit_population_with_completeness_and_accuracy_file, http_client
):
    # fmt: off
    completeness_and_accuracy = audit_population_with_completeness_and_accuracy_file \
        .completeness_accuracy.first()
    # fmt: on
    response = _download_population_completeness_and_accuracy_file(
        http_client,
        {
            'auditId': audit_population_with_completeness_and_accuracy_file.audit.id,
            'populationId': '',
            'fileId': completeness_and_accuracy.id,
        },
    )
    assert response.status_code == HttpResponseBadRequest().status_code


@pytest.mark.functional(permissions=['population.view_populationcompletenessaccuracy'])
def test_download_population_completeness_and_accuracy_file_without_file_id(
    audit_population_with_completeness_and_accuracy_file, http_client
):
    response = _download_population_completeness_and_accuracy_file(
        http_client,
        {
            'auditId': audit_population_with_completeness_and_accuracy_file.audit.id,
            'populationId': audit_population_with_completeness_and_accuracy_file.id,
            'fileId': '',
        },
    )
    assert response.status_code == HttpResponseBadRequest().status_code

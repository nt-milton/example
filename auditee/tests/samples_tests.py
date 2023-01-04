import os

import pytest

from auditee.tests.mutations import ADD_EVIDENCE_ATTACHMENT
from auditee.tests.queries import GET_AUDITEE_EVIDENCE
from population.models import AuditPopulation, AuditPopulationEvidence, Evidence, Sample

template_seed_file_path = f'{os.path.dirname(__file__)}/resources/template_seed.xlsx'


@pytest.fixture
def audit_population_evidence(
    audit_population: AuditPopulation, sample_evidence: Evidence
) -> AuditPopulationEvidence:
    return AuditPopulationEvidence.objects.create(
        population=audit_population, evidence_request=sample_evidence
    )


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_samples_evidence_request_order(
    graphql_client,
    audit_population_with_samples,
):
    response = graphql_client.execute(
        GET_AUDITEE_EVIDENCE,
        variables={'evidenceId': '1', 'auditId': '1', 'isEvidenceDetail': True},
    )

    evidence_response = response['data']['auditeeEvidence']
    samples = evidence_response['samples']
    assert evidence_response['id'] == '1'
    assert len(samples) == 3
    assert samples[0]['name'] == 'Joseph'
    assert samples[1]['name'] == 'Jotaro'
    assert samples[2]['name'] == 'Josuke'


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_samples_evidence_attach_files_correctly(
    graphql_client, sample_evidence, sample_evidence_2, population_data_sample
):
    pop_data = population_data_sample.first()
    sample1 = Sample.objects.create(
        evidence_request=sample_evidence, population_data=pop_data
    )
    sample2 = Sample.objects.create(
        evidence_request=sample_evidence_2, population_data=pop_data
    )

    add_attachment_input = {
        'input': dict(
            id=str(sample_evidence.id),
            timeZone='UTC',
            sampleId=str(sample1.id),
            uploadedFiles=[
                {'fileName': 'evidence.txt', 'file': "b'RXZpZGVuY2UgZmlsZQ=='"}
            ],
        )
    }

    graphql_client.execute(ADD_EVIDENCE_ATTACHMENT, variables=add_attachment_input)

    assert Sample.objects.filter(population_data=pop_data).count() == 2
    assert sample1.attachments.count() == 1
    assert sample2.attachments.count() == 0

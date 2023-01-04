import pytest

from audit.models import Audit, AuditStatus
from auditor.tests.mutations import (
    ADD_AUDITOR_POPULATION_SAMPLE,
    ATTACH_SAMPLE_TO_EVIDENCE_REQUEST,
    CREATE_AUDITOR_POPULATION_SAMPLE,
    CREATE_AUDITOR_SAMPLE_SIZE,
    DELETE_AUDITOR_POPULATION_SAMPLE,
)
from auditor.tests.queries import AUDITOR_POPULATION_DATA, GET_AUDITOR_EVIDENCE_DETAILS
from fieldwork.models import Evidence
from fieldwork.tests.utils_tests import create_evidence_attachment
from population.models import (
    AuditPopulation,
    AuditPopulationEvidence,
    PopulationData,
    Sample,
)
from population.utils import set_sample_name


@pytest.fixture
def audit(audit) -> Audit:
    AuditStatus.objects.create(
        audit=audit,
        requested=True,
        initiated=True,
        fieldwork=True,
        in_draft_report=True,
    )

    return audit


@pytest.fixture
def sample_evidence_with_attch(
    graphql_organization, audit, sample, sample_evidence
) -> Evidence:
    create_evidence_attachment(graphql_organization, sample_evidence)
    create_evidence_attachment(
        graphql_organization,
        sample_evidence,
        sample_id=sample.id,
        file_name='Sample attachment',
    )

    return sample_evidence


@pytest.fixture
def audit_population_evidence(
    audit_population: AuditPopulation, sample_evidence_with_attch: Evidence
) -> AuditPopulationEvidence:
    return AuditPopulationEvidence.objects.create(
        population=audit_population, evidence_request=sample_evidence_with_attch
    )


@pytest.fixture
def population_data(audit_population):
    for i in range(10):
        PopulationData.objects.create(data='{}', population=audit_population)

    return PopulationData.objects.all()


@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_not_attach_sample_to_evidence_request_is_deleted(
    graphql_audit_client, audit_population_evidence, population_data_sample
):
    audit_population_evidence.evidence_request.er_type = 'sample_er'
    audit_population_evidence.evidence_request.is_deleted = True
    audit_population_evidence.evidence_request.save()
    response = graphql_audit_client.execute(
        ATTACH_SAMPLE_TO_EVIDENCE_REQUEST,
        variables={
            "input": {
                "auditId": audit_population_evidence.population.audit.id,
                "populationId": audit_population_evidence.population.id,
            }
        },
    )

    evidence_request_attached = response['data']['attachSampleToEvidenceRequest'][
        'evidenceRequest'
    ]
    assert len(evidence_request_attached) == 0
    assert (
        Sample.objects.filter(
            evidence_request=audit_population_evidence.evidence_request
        ).count()
    ) == 0


@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_attach_sample_to_evidence_request(
    graphql_audit_client, audit_population_evidence, population_data_sample
):
    audit_population_evidence.evidence_request.er_type = 'sample_er'
    audit_population_evidence.evidence_request.save()
    response = graphql_audit_client.execute(
        ATTACH_SAMPLE_TO_EVIDENCE_REQUEST,
        variables={
            "input": {
                "auditId": audit_population_evidence.population.audit.id,
                "populationId": audit_population_evidence.population.id,
            }
        },
    )

    evidence_request_attached = response['data']['attachSampleToEvidenceRequest'][
        'evidenceRequest'
    ]
    assert len(evidence_request_attached) == 1
    assert (
        Sample.objects.filter(
            evidence_request=audit_population_evidence.evidence_request
        ).count()
    ) == len(population_data_sample)


@pytest.mark.functional(
    permissions=['population.view_auditpopulation', 'population.change_auditpopulation']
)
def test_generate_population_sample_with_only_selected_items(
    graphql_audit_client, audit_population, population_data
):
    graphql_audit_client.execute(
        CREATE_AUDITOR_POPULATION_SAMPLE,
        variables={
            'input': {
                'auditId': audit_population.audit.id,
                'populationId': audit_population.id,
                'sampleSize': 2,
                'populationDataIds': ["1", "2"],
            }
        },
    )

    response = graphql_audit_client.execute(
        AUDITOR_POPULATION_DATA,
        variables={
            'auditId': audit_population.audit.id,
            'populationId': audit_population.id,
            'isSample': True,
        },
    )

    updated_population = AuditPopulation.objects.get(id=audit_population.id)
    sample = response['data']['auditorPopulationData']['populationData']
    assert sample[0]['id'] == '1'
    assert sample[1]['id'] == '2'
    assert len(sample) == 2
    assert updated_population.sample_size == 2


@pytest.mark.functional(
    permissions=['population.view_auditpopulation', 'population.change_auditpopulation']
)
def test_generate_population_sample_with_more_selected_items(
    graphql_audit_client, audit_population, population_data
):
    graphql_audit_client.execute(
        CREATE_AUDITOR_POPULATION_SAMPLE,
        variables={
            'input': {
                'auditId': audit_population.audit.id,
                'populationId': audit_population.id,
                'sampleSize': 2,
                'populationDataIds': ["1", "2", "3"],
            }
        },
    )

    response = graphql_audit_client.execute(
        AUDITOR_POPULATION_DATA,
        variables={
            'auditId': audit_population.audit.id,
            'populationId': audit_population.id,
            'isSample': True,
        },
    )

    updated_population = AuditPopulation.objects.get(id=audit_population.id)
    sample = response['data']['auditorPopulationData']['populationData']
    assert sample[0]['id'] == '1'
    assert sample[1]['id'] == '2'
    assert sample[2]['id'] == '3'
    assert len(sample) == 3
    assert updated_population.sample_size == 3


@pytest.mark.functional(
    permissions=['population.view_auditpopulation', 'population.change_auditpopulation']
)
def test_generate_population_sample_with_selected_items(
    graphql_audit_client, audit_population, population_data
):
    graphql_audit_client.execute(
        CREATE_AUDITOR_POPULATION_SAMPLE,
        variables={
            'input': {
                'auditId': audit_population.audit.id,
                'populationId': audit_population.id,
                'sampleSize': 5,
                'populationDataIds': ["1", "2", "3"],
            }
        },
    )

    response = graphql_audit_client.execute(
        AUDITOR_POPULATION_DATA,
        variables={
            'auditId': audit_population.audit.id,
            'populationId': audit_population.id,
            'isSample': True,
        },
    )

    updated_population = AuditPopulation.objects.get(id=audit_population.id)
    sample = response['data']['auditorPopulationData']['populationData']
    assert sample[0]['id'] == '1'
    assert sample[1]['id'] == '2'
    assert sample[2]['id'] == '3'
    assert len(sample) == 5
    assert updated_population.sample_size == 5


@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_add_population_sample_all_already_added(
    graphql_audit_client, audit_population
):
    PopulationData.objects.create(
        data={"name": "Joseph"}, population=audit_population, is_sample=True
    )

    response = graphql_audit_client.execute(
        ADD_AUDITOR_POPULATION_SAMPLE,
        variables={
            "input": {
                "auditId": audit_population.audit.id,
                "populationId": audit_population.id,
            }
        },
    )
    error = response['errors'][0]
    assert error['message'] == 'There are no more available items to add'


@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_add_population_sample(graphql_audit_client, audit_population, population_data):
    graphql_audit_client.execute(
        ADD_AUDITOR_POPULATION_SAMPLE,
        variables={
            "input": {
                "auditId": audit_population.audit.id,
                "populationId": audit_population.id,
            }
        },
    )

    assert (
        PopulationData.objects.filter(
            is_sample=True, population__id=audit_population.id
        ).count()
        == 1
    )


@pytest.mark.functional(permissions=['population.delete_auditpopulation'])
def test_delete_population_sample(
    graphql_audit_client, audit_population, population_data_sample
):
    ids = PopulationData.objects.values_list('id', flat=True).filter(
        is_sample=True, population__id=audit_population.id
    )

    response = graphql_audit_client.execute(
        DELETE_AUDITOR_POPULATION_SAMPLE,
        variables={
            "input": {
                "auditId": audit_population.audit.id,
                "populationId": audit_population.id,
                "sampleIds": ids,
            }
        },
    )

    assert (
        PopulationData.objects.filter(
            is_sample=True, population__id=audit_population.id
        ).count()
        == 0
    )

    samples = response['data']['deleteAuditorPopulationSample']
    assert len(samples['samples']) == 3


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_samples_evidence_request_order(
    graphql_audit_client,
    audit_soc2_type2,
    sample_evidence,
    audit_population_with_samples,
    audit_population_evidence,
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_EVIDENCE_DETAILS,
        variables={
            'evidenceId': audit_population_evidence.evidence_request.id,
            'auditId': audit_soc2_type2.id,
            'isEvidenceDetail': True,
        },
    )

    evidence_response = response['data']['auditorEvidence']
    samples = evidence_response['samples']
    assert evidence_response['id'] == '1'
    assert len(samples) == 3
    assert samples[0]['name'] == 'Joseph'
    assert samples[1]['name'] == 'Jotaro'
    assert samples[2]['name'] == 'Josuke'


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_samples_evidence_request_not_getting_null(
    graphql_audit_client,
    audit_soc2_type2,
    sample_evidence,
    audit_population_with_samples,
    audit_population_evidence,
):
    evidence_request = audit_population_evidence.evidence_request
    sample = Sample.objects.filter(evidence_request=evidence_request).first()
    sample.population_data = None
    sample.save()
    response = graphql_audit_client.execute(
        GET_AUDITOR_EVIDENCE_DETAILS,
        variables={
            'evidenceId': evidence_request.id,
            'auditId': audit_soc2_type2.id,
            'isEvidenceDetail': True,
        },
    )

    evidence_response = response['data']['auditorEvidence']
    samples = evidence_response['samples']

    assert evidence_response['id'] == '1'
    assert len(samples) == 2
    assert Sample.objects.filter(evidence_request=evidence_request).count() == 3


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_samples_evidence_request_delete_relationship(
    graphql_audit_client,
    audit_soc2_type2,
    sample_evidence,
    audit_population_with_samples,
    audit_population_evidence,
):
    evidence_request = audit_population_evidence.evidence_request
    population = audit_population_with_samples.population
    population_data = PopulationData.objects.filter(population=population).first()
    population_data.delete()
    response = graphql_audit_client.execute(
        GET_AUDITOR_EVIDENCE_DETAILS,
        variables={
            'evidenceId': evidence_request.id,
            'auditId': audit_soc2_type2.id,
            'isEvidenceDetail': True,
        },
    )

    evidence_response = response['data']['auditorEvidence']
    samples = evidence_response['samples']

    assert evidence_response['id'] == '1'
    assert len(samples) == 2
    assert Sample.objects.filter(evidence_request=evidence_request).count() == 2


@pytest.mark.functional(
    permissions=['population.view_auditpopulation', 'population.change_auditpopulation']
)
def test_remove_population_sample(
    graphql_audit_client, audit_population, population_data
):
    graphql_audit_client.execute(
        CREATE_AUDITOR_POPULATION_SAMPLE,
        variables={
            'input': {
                'auditId': audit_population.audit.id,
                'populationId': audit_population.id,
                'sampleSize': 4,
                'populationDataIds': [],
            }
        },
    )

    assert (
        PopulationData.objects.filter(
            is_sample=True, population__id=audit_population.id
        ).count()
        == 4
    )

    PopulationData.remove_sample(audit_population.id)

    assert (
        PopulationData.objects.filter(
            is_sample=True, population__id=audit_population.id
        ).count()
        == 0
    )


@pytest.mark.functional(
    permissions=['population.view_auditpopulation', 'population.change_auditpopulation']
)
def test_get_population_sample(graphql_audit_client, audit_population, population_data):
    graphql_audit_client.execute(
        CREATE_AUDITOR_POPULATION_SAMPLE,
        variables={
            'input': {
                'auditId': audit_population.audit.id,
                'populationId': audit_population.id,
                'sampleSize': 4,
                'populationDataIds': [],
            }
        },
    )

    response = graphql_audit_client.execute(
        AUDITOR_POPULATION_DATA,
        variables={
            'auditId': audit_population.audit.id,
            'populationId': audit_population.id,
            'isSample': True,
        },
    )

    updated_population = AuditPopulation.objects.get(id=audit_population.id)
    sample = response['data']['auditorPopulationData']['populationData']
    assert len(sample) == 4
    assert updated_population.sample_size == 4
    assert (
        PopulationData.objects.filter(
            is_sample=True, population__id=audit_population.id
        ).count()
        == 4
    )


@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_generate_population_sample_invalid_sample_size(
    graphql_audit_client, audit_population, population_data
):
    response = graphql_audit_client.execute(
        CREATE_AUDITOR_POPULATION_SAMPLE,
        variables={
            'input': {
                'auditId': audit_population.audit.id,
                'populationId': audit_population.id,
                'sampleSize': 0,
                'populationDataIds': [],
            }
        },
    )

    error_message = response['errors'][0]['message']

    assert error_message == f'Invalid sample size population {audit_population.id}'

    population_count = PopulationData.objects.filter(
        population_id=audit_population.id
    ).count()
    response = graphql_audit_client.execute(
        CREATE_AUDITOR_POPULATION_SAMPLE,
        variables={
            'input': {
                'auditId': audit_population.audit.id,
                'populationId': audit_population.id,
                'sampleSize': population_count + 1,
                'populationDataIds': [],
            }
        },
    )

    assert error_message == f'Invalid sample size population {audit_population.id}'


@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_generate_population_sample_size(
    graphql_audit_client, audit_population, population_data
):
    graphql_audit_client.execute(
        CREATE_AUDITOR_SAMPLE_SIZE,
        variables={
            'input': {
                'auditId': audit_population.audit.id,
                'populationId': audit_population.id,
            }
        },
    )

    population = AuditPopulation.objects.first()
    assert population.sample_size == 2


@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_generate_population_sample(
    graphql_audit_client, audit_population, population_data
):
    graphql_audit_client.execute(
        CREATE_AUDITOR_POPULATION_SAMPLE,
        variables={
            'input': {
                'auditId': audit_population.audit.id,
                'populationId': audit_population.id,
                'sampleSize': 4,
                'populationDataIds': [],
            }
        },
    )
    assert PopulationData.objects.filter(is_sample=True).count() == 4


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_sample_er(
    graphql_audit_client,
    audit_soc2_type2,
    sample_evidence_with_attch,
    population_data_sample,
    audit_population_evidence,
):
    audit_population_evidence.evidence_request.population_sample.set(
        population_data_sample
    )

    response = graphql_audit_client.execute(
        GET_AUDITOR_EVIDENCE_DETAILS,
        variables={
            'evidenceId': audit_population_evidence.evidence_request.id,
            'auditId': audit_soc2_type2.id,
            'isEvidenceDetail': True,
        },
    )
    samples = response['data']['auditorEvidence']['samples']
    additional_attachments = response['data']['auditorEvidence']['attachments']

    assert len(samples) == 3
    assert len(additional_attachments) == 1


@pytest.mark.django_db
def test_set_sample_name(pop1_population_data, sample_evidence):
    sample_evidence.population_sample.set([pop1_population_data])
    sample = Sample.objects.filter(evidence_request=sample_evidence).first()

    set_sample_name(sample)
    assert sample.name == 'John Doe'


@pytest.mark.django_db
def test_set_sample_name_no_population_data(sample, sample_evidence):
    sample.evidence_request = sample_evidence
    sample.save()

    set_sample_name(sample)
    assert sample.name == ''

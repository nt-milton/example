import os

import pytest
from django.core.files import File
from graphene.test import Client

from audit.constants import AUDIT_FIRMS
from audit.models import Audit, AuditAuditor, AuditFirm, AuditorAuditFirm, AuditStatus
from audit.tests.factory import create_audit, create_audit_firm
from auditor.tests.mutations import (
    DELETE_AUDITOR_COMPLETENESS_ACCURACY,
    UPDATE_AUDITOR_COMPLETENESS_ACCURACY,
    UPDATE_AUDITOR_POPULATION,
)
from auditor.tests.queries import (
    AUDITOR_GET_COMPLETENESS_ACCURACY,
    AUDITOR_POPULATION_DATA,
    GET_AUDITOR_AUDIT_POPULATION,
    GET_AUDITOR_AUDIT_POPULATIONS,
)
from fieldwork.models import Evidence
from fieldwork.tests.utils_tests import create_evidence_attachment
from population.constants import POPULATION_STATUS_DICT
from population.models import (
    AuditPopulation,
    AuditPopulationEvidence,
    AuditPopulationSample,
    PopulationCompletenessAccuracy,
    PopulationData,
    Sample,
)
from user.models import Auditor, User

template_seed_file_path = f'{os.path.dirname(__file__)}/resources/template_seed.xlsx'


@pytest.fixture
def laika_audit_firm():
    return create_audit_firm(AUDIT_FIRMS[0])


@pytest.fixture
def laika_audit(graphql_organization, laika_audit_firm):
    return create_audit(
        organization=graphql_organization,
        name='Laika Dev Soc 2 Type 1 Audit 2021',
        audit_firm=laika_audit_firm,
    )


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
def auditor(audit: Audit, graphql_audit_user: User) -> Auditor:
    auditor = Auditor(user=graphql_audit_user)
    auditor.save(is_not_django=True)
    AuditAuditor.objects.create(audit=audit, auditor=auditor)

    return auditor


@pytest.fixture
def auditor_audit_firm(
    auditor: Auditor, graphql_audit_firm: AuditFirm
) -> AuditorAuditFirm:
    auditor_audit_firm = AuditorAuditFirm.objects.create(
        auditor=auditor, audit_firm=graphql_audit_firm
    )

    return auditor_audit_firm


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
def audit_population_sample(
    audit: Audit,
    sample: Sample,
    audit_population: AuditPopulation,
    audit_population_evidence: AuditPopulationEvidence,
) -> AuditPopulationSample:
    audit_population_sample = AuditPopulationSample.objects.create(
        population=audit_population, sample=sample
    )

    return audit_population_sample


@pytest.fixture
def audit_population_submitted(audit: Audit) -> AuditPopulation:
    population = AuditPopulation.objects.create(
        audit=audit,
        display_id='POP-2',
        name='Name test 2',
        instructions='Instructions test',
        status='submitted',
        description='description test',
    )

    return population


@pytest.fixture
def audit_population_accepted(audit: Audit) -> AuditPopulation:
    population = AuditPopulation.objects.create(
        audit=audit,
        display_id='POP-3',
        name='Name test 3',
        instructions='Instructions test',
        status='accepted',
        description='description test',
    )

    return population


@pytest.fixture
def audit_population_auditor_not_in_firm(laika_audit: Audit) -> AuditPopulation:
    population = AuditPopulation.objects.create(
        audit=laika_audit,
        name='Name test',
        instructions='Instructions test',
        description='description test',
    )

    return population


@pytest.fixture
def completeness_accuracy_file(audit_population):
    return PopulationCompletenessAccuracy.objects.create(
        population=audit_population,
        name='template_seed.xlsx',
        file=File(open(template_seed_file_path, "rb")),
    )


@pytest.fixture
def completeness_accuracy_file_not_in_audit_firm(audit_population_auditor_not_in_firm):
    return PopulationCompletenessAccuracy.objects.create(
        population=audit_population_auditor_not_in_firm,
        name='template_seed.xlsx',
        file=File(open(template_seed_file_path, "rb")),
    )


@pytest.fixture
def population_data(audit_population):
    for i in range(10):
        PopulationData.objects.create(data='{}', population=audit_population)

    return PopulationData.objects.all()


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_auditor_audit_population(
    graphql_audit_client: Client,
    audit_soc2_type2: Audit,
    audit_population: AuditPopulation,
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_AUDIT_POPULATION,
        variables={'auditId': audit_soc2_type2.id, 'populationId': audit_population.id},
    )
    assert len(response['data']) == 1
    assert response['data']['auditorAuditPopulation']['name'] == 'Name test'


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_auditor_audit_population_recommeded_sample_size_is_at_least_1(
    graphql_audit_client: Client,
    audit_soc2_type2: Audit,
    audit_population: AuditPopulation,
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_AUDIT_POPULATION,
        variables={'auditId': audit_soc2_type2.id, 'populationId': audit_population.id},
    )
    assert response['data']['auditorAuditPopulation']['recommendedSampleSize'] == 1


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_auditor_audit_population_recommeded_sample_size_is_25_percent_of_data(
    graphql_audit_client: Client,
    audit_soc2_type2: Audit,
    audit_population: AuditPopulation,
    population_data,
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_AUDIT_POPULATION,
        variables={'auditId': audit_soc2_type2.id, 'populationId': audit_population.id},
    )
    assert response['data']['auditorAuditPopulation']['recommendedSampleSize'] == 2


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_auditor_audit_population_is_not_in_audit_firm(
    graphql_audit_client: Client,
    laika_audit: Audit,
    audit_population_auditor_not_in_firm: AuditPopulation,
):
    expected_error = f'Auditor can not view audit population for audit {laika_audit.id}'

    response = graphql_audit_client.execute(
        GET_AUDITOR_AUDIT_POPULATION,
        variables={
            'auditId': laika_audit.id,
            'populationId': audit_population_auditor_not_in_firm.id,
        },
    )
    assert response['errors'][0]['message'] == expected_error


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
@pytest.mark.skipif(
    True,
    reason='''We can not test this because sqlite3
                                    does not support regex operations''',
)
def test_get_auditor_audit_populations(
    graphql_audit_client,
    audit,
    audit_population,
    audit_population_submitted,
    audit_population_accepted,
    graphql_audit_user,
    auditor_audit_firm,
):
    graphql_audit_user.role = 'AuditorAdmin'
    graphql_audit_user.save()

    response = graphql_audit_client.execute(
        GET_AUDITOR_AUDIT_POPULATIONS,
        variables={
            'auditId': audit.id,
        },
    )
    data = response['data']['auditorAuditPopulations']
    assert len(data['open']) == 1
    assert len(data['submitted']) == 2
    assert data['open'][0].get('display_id') == 'POP-1'
    assert data['submitted'][0].get('display_id') == 'POP-2'
    assert data['submitted'][1].get('display_id') == 'POP-3'


@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_update_population_status(
    graphql_audit_client, audit, audit_population_submitted
):
    assert audit_population_submitted.times_moved_back_to_open == 0

    graphql_audit_client.execute(
        UPDATE_AUDITOR_POPULATION,
        variables={
            'input': {
                'auditId': audit.id,
                'populationId': audit_population_submitted.id,
                'fields': [
                    {'field': 'status', 'value': POPULATION_STATUS_DICT['Open']}
                ],
            }
        },
    )

    updated_population = AuditPopulation.objects.get(id=audit_population_submitted.id)

    assert (
        updated_population.times_moved_back_to_open
        == audit_population_submitted.times_moved_back_to_open + 1
    )
    assert updated_population.status == POPULATION_STATUS_DICT['Open']


@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_audit_population_track_times_moved_back_to_open(
    audit, audit_population_accepted
):
    initial_times_moved_back_to_open = (
        audit_population_accepted.times_moved_back_to_open
    )

    assert initial_times_moved_back_to_open == 0

    times_moved_back_to_open = audit_population_accepted.track_times_moved_back_to_open(
        new_status=POPULATION_STATUS_DICT['Open']
    )

    assert times_moved_back_to_open == initial_times_moved_back_to_open + 1


@pytest.mark.functional(permissions=['population.view_populationcompletenessaccuracy'])
def test_auditor_population_completeness_accuracy(
    graphql_audit_client, audit_soc2_type2, completeness_accuracy_file
):
    response = graphql_audit_client.execute(
        AUDITOR_GET_COMPLETENESS_ACCURACY,
        variables={
            'auditId': audit_soc2_type2.id,
            'populationId': completeness_accuracy_file.population.id,
        },
    )

    data = response['data']['auditorPopulationCompletenessAccuracy']

    assert len(data) == 1
    assert data[0]['name'] == 'template_seed.xlsx'


@pytest.mark.functional(permissions=['population.view_populationcompletenessaccuracy'])
def test_auditor_population_completeness_accuracy_fails_if_user_not_in_audit(
    graphql_audit_client,
    graphql_audit_user,
    laika_audit,
    completeness_accuracy_file_not_in_audit_firm,
):
    response = graphql_audit_client.execute(
        AUDITOR_GET_COMPLETENESS_ACCURACY,
        variables={
            'auditId': laika_audit.id,
            'populationId': completeness_accuracy_file_not_in_audit_firm.population.id,
        },
    )

    error_message = response['errors'][0]['message']

    assert (
        error_message
        == f'Auditor with id: {graphql_audit_user.id} '
        'can not get completeness '
        f'and accuracy files for audit {laika_audit.id}'
    )


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_population_data_counter(
    graphql_audit_client: Client,
    audit_soc2_type2: Audit,
    audit_population: AuditPopulation,
    population_data: PopulationData,
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_AUDIT_POPULATION,
        variables={'auditId': audit_soc2_type2.id, 'populationId': audit_population.id},
    )

    data = response['data']
    assert len(data) == 1
    assert data['auditorAuditPopulation']['populationDataCounter'] == 10


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_population_data_counter_zero_value(
    graphql_audit_client: Client,
    audit_soc2_type2: Audit,
    audit_population: AuditPopulation,
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_AUDIT_POPULATION,
        variables={'auditId': audit_soc2_type2.id, 'populationId': audit_population.id},
    )
    data = response['data']
    assert len(data) == 1
    assert data['auditorAuditPopulation']['populationDataCounter'] == 0


@pytest.mark.parametrize('data_length, with_pagination', [(2, True), (3, False)])
@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_population_data_paginated(
    graphql_audit_client,
    audit_population,
    data_length,
    with_pagination,
    population_data_sample,
):
    response = graphql_audit_client.execute(
        AUDITOR_POPULATION_DATA,
        variables={
            "auditId": audit_population.audit.id,
            "populationId": audit_population.id,
            "pagination": {"page": 1, "pageSize": 2} if with_pagination else None,
        },
    )
    pop_data = response['data']['auditorPopulationData']
    data = pop_data['populationData']
    pagination = pop_data['pagination']

    assert len(data) == data_length
    if with_pagination:
        assert pagination['page'] == 1
        assert pagination['pages'] == 2
    else:
        assert not pagination


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_population_data_filtered(
    graphql_audit_client, audit_population, population_data_sample
):
    response = graphql_audit_client.execute(
        AUDITOR_POPULATION_DATA,
        variables={
            "auditId": audit_population.audit.id,
            "populationId": audit_population.id,
            "searchCriteria": 'Jos',
        },
    )
    pop_data = response['data']['auditorPopulationData']
    data = pop_data['populationData']

    assert len(data) == 2


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_laika_source_population_data_filtered(
    graphql_audit_client,
    audit_population_people_source_pop_2,
    laika_source_population_data_sample,
):
    response = graphql_audit_client.execute(
        AUDITOR_POPULATION_DATA,
        variables={
            "auditId": audit_population_people_source_pop_2.audit.id,
            "populationId": audit_population_people_source_pop_2.id,
            "searchCriteria": 'Jos',
        },
    )
    pop_data = response['data']['auditorPopulationData']
    data = pop_data['populationData']

    assert len(data) == 2


@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_update_population_configuration_filters(
    graphql_audit_client, audit, audit_population_submitted
):
    assert audit_population_submitted.configuration_filters is None

    graphql_audit_client.execute(
        UPDATE_AUDITOR_POPULATION,
        variables={
            'input': {
                'auditId': audit.id,
                'populationId': audit_population_submitted.id,
                'fields': [
                    {
                        'field': 'configuration_filters',
                        'jsonList': [
                            '{"id": "Hire Date", "value": ["2022-06-01", "2022-06-30"],'
                            ' "column": "Hire Date", "component": "dateRangePicker",'
                            ' "condition": "is_between", "columnType": "DATE"}'
                        ],
                    }
                ],
            }
        },
    )

    updated_population = AuditPopulation.objects.get(id=audit_population_submitted.id)
    assert updated_population.configuration_filters == [
        {
            "id": "Hire Date",
            "value": ["2022-06-01", "2022-06-30"],
            "column": "Hire Date",
            "component": "dateRangePicker",
            "condition": "is_between",
            "columnType": "DATE",
        }
    ]


@pytest.mark.functional(
    permissions=['population.change_populationcompletenessaccuracy']
)
def test_update_auditor_population_completeness_file(
    graphql_audit_client, audit_population, completeness_accuracy_file
):
    new_name = 'Updated name.pdf'
    graphql_audit_client.execute(
        UPDATE_AUDITOR_COMPLETENESS_ACCURACY,
        variables={
            'input': dict(
                auditId=audit_population.audit.id,
                populationId=audit_population.id,
                id=completeness_accuracy_file.id,
                newName=new_name,
            )
        },
    )

    completeness_accuracy = PopulationCompletenessAccuracy.objects.get(
        id=completeness_accuracy_file.id
    )

    assert completeness_accuracy.name == new_name


@pytest.mark.functional(
    permissions=['population.change_populationcompletenessaccuracy']
)
def test_update_auditor_population_completeness_file_unique_name(
    graphql_audit_client, audit_population, completeness_accuracy_file
):
    PopulationCompletenessAccuracy.objects.create(
        population=audit_population,
        name='new_seed.xlsx',
        file=File(open(template_seed_file_path, "rb")),
    )
    new_name = 'new_seed.xlsx'
    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_COMPLETENESS_ACCURACY,
        variables={
            'input': dict(
                auditId=audit_population.audit.id,
                populationId=audit_population.id,
                id=completeness_accuracy_file.id,
                newName=new_name,
            )
        },
    )
    error = response['errors'][0]
    assert error['message'] == 'This file name already exists. Use a different name.'


@pytest.mark.functional(
    permissions=['population.delete_populationcompletenessaccuracy']
)
def test_delete_auditor_population_completeness_file(
    graphql_audit_client, audit_population, completeness_accuracy_file
):
    graphql_audit_client.execute(
        DELETE_AUDITOR_COMPLETENESS_ACCURACY,
        variables={
            'input': dict(
                auditId=audit_population.audit.id,
                populationId=audit_population.id,
                id=completeness_accuracy_file.id,
            )
        },
    )

    completeness_accuracy = PopulationCompletenessAccuracy.objects.get(
        id=completeness_accuracy_file.id
    )

    assert completeness_accuracy.is_deleted


@pytest.mark.django_db
@pytest.mark.skipif(True, reason='TDD for FZ-2258')
def test_laika_source_data_exists(
    graphql_client, graphql_organization, graphql_user, audit_population
):
    audit_population.default_source = 'People'
    audit_population.save()

    data_detected = audit_population.laika_source_data_exists()

    assert data_detected is True

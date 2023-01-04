import os
from datetime import datetime

import pytest
from django.core.files import File

from audit.models import Audit
from auditee.tests.factory import create_population_comments_for_pools
from auditee.tests.mutations import (
    DELETE_POPULATION_DATA_FILE,
    UPDATE_POPULATION,
    UPLOAD_POPULATION_FILE,
)
from auditee.tests.queries import (
    AUDITEE_POPULATION_DATA,
    GET_AUDITEE_AUDIT_POPULATION,
    GET_AUDITEE_AUDIT_POPULATIONS,
    GET_AUDITEE_EVIDENCE,
)
from fieldwork.constants import ALL_POOL, LAIKA_POOL, LCL_CX_POOL, LCL_POOL
from fieldwork.models import Evidence, Requirement, RequirementEvidence
from laika.tests.utils import file_to_base64
from laika.utils.dates import MM_DD_YYYY
from organization.models import Organization
from organization.tests.factory import create_organization
from population.constants import POPULATION_STATUS_DICT
from population.models import AuditPopulation, AuditPopulationEvidence, PopulationData
from user.constants import ROLE_SUPER_ADMIN

from .test_utils import create_data_file

template_seed_file_path = f'{os.path.dirname(__file__)}/resources/template_seed.xlsx'
population_1_file_path = f'{os.path.dirname(__file__)}/resources/population_1.xlsx'
population_1_with_instructions_file_path = (
    f'{os.path.dirname(__file__)}/resources/population_1_with_instructions.xlsx'
)
invalid_population_1_file_path = (
    f'{os.path.dirname(__file__)}/resources/invalid_population_1.xlsx'
)
invalid_population_1_with_instructions_file_path = (
    f'{os.path.dirname(__file__)}/resources/invalid_population_1_with_instructions.xlsx'
)
empty_population_1_file_path = (
    f'{os.path.dirname(__file__)}/resources/empty_population_1.xlsx'
)
empty_population_1_with_instructions_file_path = (
    f'{os.path.dirname(__file__)}/resources/empty_population_1_with_instructions.xlsx'
)
empty_population_2_with_instructions_file_path = (
    f'{os.path.dirname(__file__)}/resources/empty_population_2_with_instructions.xlsx'
)
wrong_template_population_1_file_path = (
    f'{os.path.dirname(__file__)}/resources/wrong_template_population_1.xlsx'
)
missing_header_population_1_file_path = (
    f'{os.path.dirname(__file__)}/resources/missing_header_population_1.xlsx'
)
missing_header_population_1_with_instructions_file_path = (
    f'{os.path.dirname(__file__)}/resources/missing_header_pop_1_with_instructions.xlsx'
)


@pytest.fixture
def requirement_sample_evidence(
    sample_evidence: Evidence, requirement: Requirement
) -> RequirementEvidence:
    return RequirementEvidence.objects.create(
        evidence=sample_evidence, requirement=requirement
    )


@pytest.fixture
def audit_population_with_data_file(audit_soc2_type2: Audit) -> AuditPopulation:
    population = AuditPopulation.objects.create(
        audit=audit_soc2_type2,
        name='Name test',
        instructions='Instructions test',
        description='description test',
        data_file=File(open(template_seed_file_path, "rb")),
        data_file_name='template_seed.xlsx',
    )

    return population


@pytest.fixture
def audit_population_submitted(audit_soc2_type2: Audit) -> AuditPopulation:
    population = AuditPopulation.objects.create(
        audit=audit_soc2_type2,
        display_id='POP 2',
        name='Name test 2',
        instructions='Instructions test',
        status='submitted',
        description='description test',
    )

    return population


@pytest.fixture
def audit_population_accepted(audit_soc2_type2: Audit) -> AuditPopulation:
    population = AuditPopulation.objects.create(
        audit=audit_soc2_type2,
        display_id='POP 3',
        name='Name test 3',
        instructions='Instructions test',
        status='accepted',
        description='description test',
    )

    return population


@pytest.fixture
def audit_population_evidence(
    audit_population: AuditPopulation, sample_evidence: Evidence
) -> AuditPopulationEvidence:
    return AuditPopulationEvidence.objects.create(
        population=audit_population, evidence_request=sample_evidence
    )


@pytest.fixture
def organization() -> Organization:
    return create_organization(flags=[], name='Test Org')


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_auditee_audit_population(
    graphql_client,
    audit_soc2_type2,
    audit_population,
    sample_evidence,
    requirement,
    audit_population_evidence,
    requirement_sample_evidence,
):
    response = graphql_client.execute(
        GET_AUDITEE_AUDIT_POPULATION,
        variables={'auditId': audit_soc2_type2.id, 'populationId': audit_population.id},
    )

    assert len(response['data']) == 1


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_audit_evidence(graphql_client, audit_population_with_samples):
    response = graphql_client.execute(
        GET_AUDITEE_EVIDENCE, variables={'evidenceId': '1', 'auditId': '1'}
    )
    evidence_response = response['data']['auditeeEvidence']['samples']
    assert len(evidence_response) == 3


@pytest.mark.functional(permissions=['fieldwork.view_evidence'])
def test_get_audit_evidence_with_additional_files(
    graphql_client, sample_evidence_with_attachment
):
    response = graphql_client.execute(
        GET_AUDITEE_EVIDENCE,
        variables={'evidenceId': '1', 'auditId': '1', 'isEvidenceDetail': True},
    )

    evidence_response = response['data']['auditeeEvidence']

    samples = evidence_response['samples'][0]

    assert len(evidence_response['attachments']) == 1
    assert len(samples['attachments']) == 1


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_auditee_audit_population_from_other_organization(
    graphql_client,
    audit,
    audit_population,
    sample_evidence,
    requirement,
    audit_population_evidence,
    requirement_sample_evidence,
    graphql_user,
    organization,
):
    graphql_user.organization = organization
    graphql_user.save()

    expected_error = f'User {graphql_user.id} cannot view audit population'

    response = graphql_client.execute(
        GET_AUDITEE_AUDIT_POPULATION,
        variables={'auditId': audit.id, 'populationId': audit_population.id},
    )

    assert response['errors'][0]['message'] == expected_error


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
@pytest.mark.skipif(
    True,
    reason='''We can not test this because sqlite3
                                    does not support regex operations''',
)
def test_get_auditee_audit_populations(
    graphql_client,
    audit,
    audit_population,
    audit_population_submitted,
    sample_evidence,
    requirement,
    audit_population_evidence,
    requirement_sample_evidence,
    audit_population_accepted,
):
    response = graphql_client.execute(
        GET_AUDITEE_AUDIT_POPULATIONS,
        variables={
            'auditId': audit.id,
        },
    )

    data = response['data']['auditeeAuditPopulations']
    assert len(data['open']) == 1
    assert len(data['submitted']) == 2
    assert data['open'][0].get('display_id') == 'POP-1'
    assert data['submitted'][0].get('display_id') == 'POP-2'
    assert data['submitted'][1].get('display_id') == 'POP-3'


@pytest.mark.parametrize(
    'file_path', [population_1_file_path, population_1_with_instructions_file_path]
)
@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_upload_population_file(
    graphql_client, audit_soc2_type2, audit_population, file_path
):
    upload_population_file_input = {
        'input': dict(
            auditId=audit_soc2_type2.id,
            populationId=audit_population.id,
            dataFile={
                'fileName': 'population_1.xlsx',
                'file': file_to_base64(file_path),
            },
        )
    }
    response = graphql_client.execute(
        UPLOAD_POPULATION_FILE, variables=upload_population_file_input
    )
    data = response['data']['uploadAuditeePopulationFile']['uploadResult']

    assert len(data['failedRows']) == 0
    assert (data['success']) is True
    assert data['auditPopulation']['dataFileName'] == 'population_1.xlsx'
    assert data['auditPopulation']['dataFile'] is not None


@pytest.mark.parametrize(
    'file_path', [population_1_file_path, population_1_with_instructions_file_path]
)
@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_upload_population_file_save_json_data(
    graphql_client, audit_soc2_type2, audit_population, file_path
):
    upload_population_file_input = {
        'input': dict(
            auditId=audit_soc2_type2.id,
            populationId=audit_population.id,
            dataFile={
                'fileName': 'population_1.xlsx',
                'file': file_to_base64(file_path),
            },
        )
    }
    response = graphql_client.execute(
        UPLOAD_POPULATION_FILE, variables=upload_population_file_input
    )

    pop = AuditPopulation.objects.get(id=audit_population.id)
    population_data_count = PopulationData.objects.filter(
        id=audit_population.id
    ).count()
    assert (
        response['data']['uploadAuditeePopulationFile']['uploadResult']['success']
    ) is True
    assert population_data_count == 0
    assert pop.data_file_name == 'population_1.xlsx'


@pytest.mark.skipif(True, reason='TDD FZ-2206')
@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_upload_population_file_correct_date(
    graphql_client,
    audit_soc2_type2,
    audit_population,
):
    upload_population_file_input = {
        'input': dict(
            auditId=audit_soc2_type2.id,
            populationId=audit_population.id,
            dataFile={
                'fileName': 'population_1.xlsx',
                'file': file_to_base64(population_1_file_path),
            },
        )
    }
    graphql_client.execute(
        UPLOAD_POPULATION_FILE, variables=upload_population_file_input
    )

    pop_data = PopulationData.objects.filter(id=audit_population.id)

    for info in pop_data:
        date = info.data.get('Hire Date')
        try:
            datetime.strptime(date, MM_DD_YYYY)
        except Exception as exc:
            assert False, f'date not formatted {exc}'


@pytest.mark.parametrize(
    'file_path',
    [invalid_population_1_file_path, invalid_population_1_with_instructions_file_path],
)
@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_upload_invalid_population_file(
    graphql_client, audit_soc2_type2, audit_population, file_path
):
    upload_population_file_input = {
        'input': dict(
            auditId=audit_soc2_type2.id,
            populationId=audit_population.id,
            dataFile={
                'fileName': 'population_1.xlsx',
                'file': file_to_base64(file_path),
            },
        )
    }
    response = graphql_client.execute(
        UPLOAD_POPULATION_FILE, variables=upload_population_file_input
    )

    data = response['data']['uploadAuditeePopulationFile']['uploadResult']

    assert len(data['failedRows']) > 0
    assert (data['success']) is False
    assert data['auditPopulation'] is None


@pytest.mark.parametrize(
    'file_path',
    [empty_population_1_file_path, empty_population_1_with_instructions_file_path],
)
@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_upload_empty_population_file(
    graphql_client, audit_soc2_type2, audit_population, file_path
):
    upload_population_file_input = {
        'input': dict(
            auditId=audit_soc2_type2.id,
            populationId=audit_population.id,
            dataFile={
                'fileName': 'population_1.xlsx',
                'file': file_to_base64(file_path),
            },
        )
    }
    response = graphql_client.execute(
        UPLOAD_POPULATION_FILE, variables=upload_population_file_input
    )

    errors = response['errors'][0]

    assert errors['message'] == "File can't be uploaded because it is empty."


@pytest.mark.parametrize(
    'file_path',
    [
        wrong_template_population_1_file_path,
        empty_population_2_with_instructions_file_path,
    ],
)
@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_upload_wrong_template_population_file(
    graphql_client, audit_soc2_type2, audit_population, file_path
):
    upload_population_file_input = {
        'input': dict(
            auditId=audit_soc2_type2.id,
            populationId=audit_population.id,
            dataFile={
                'fileName': 'population_1.xlsx',
                'file': file_to_base64(file_path),
            },
        )
    }
    response = graphql_client.execute(
        UPLOAD_POPULATION_FILE, variables=upload_population_file_input
    )

    errors = response['errors'][0]

    assert (
        errors['message']
        == 'Incorrect file. This population only '
        'accepts the template for Current Employees.'
    )


@pytest.mark.parametrize(
    'file_path',
    [
        missing_header_population_1_file_path,
        missing_header_population_1_with_instructions_file_path,
    ],
)
@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_upload_missing_header_population_file(
    graphql_client, audit_soc2_type2, audit_population, file_path
):
    upload_population_file_input = {
        'input': dict(
            auditId=audit_soc2_type2.id,
            populationId=audit_population.id,
            dataFile={
                'fileName': 'population_1.xlsx',
                'file': file_to_base64(file_path),
            },
        )
    }
    response = graphql_client.execute(
        UPLOAD_POPULATION_FILE, variables=upload_population_file_input
    )

    errors = response['errors'][0]

    assert (
        errors['message']
        == 'File is missing the section for Job Title. See template in instructions.'
    )


@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_delete_population_data_file(
    graphql_client, audit_soc2_type2, audit_population, population_data
):
    assert PopulationData.objects.count() == 1

    audit_population.data_file = create_data_file()
    delete_population_data_file_input = {
        'input': dict(auditId=audit_soc2_type2.id, populationId=audit_population.id)
    }

    response = graphql_client.execute(
        DELETE_POPULATION_DATA_FILE, variables=delete_population_data_file_input
    )
    assert (
        response['data']['deleteAuditeePopulationDataFile']['auditPopulation']['id']
    ) == str(audit_population.id)
    assert PopulationData.objects.count() == 1


@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_update_population_data_file_name(
    graphql_client,
    audit_soc2_type2,
    audit_population_with_data_file,
):
    update_population_data_file_name_input = {
        'input': dict(
            auditId=audit_soc2_type2.id,
            populationId=audit_population_with_data_file.id,
            fields=[{'field': 'data_file_name', 'value': 'MySeedFileUpdated.xlsx'}],
        )
    }

    response = graphql_client.execute(
        UPDATE_POPULATION, variables=update_population_data_file_name_input
    )
    assert (
        response['data']['updateAuditeePopulation']['auditPopulation']['dataFileName']
    ) == 'MySeedFileUpdated.xlsx'


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
@pytest.mark.skipif(
    True,
    reason='''We can not test this because sqlite3
                                    does not support regex operations''',
)
def test_get_auditee_audit_populations_comments_from_admin_pools(
    graphql_client,
    graphql_user,
    audit,
    audit_population,
    audit_population_submitted,
    comment,
):
    graphql_user.role = ROLE_SUPER_ADMIN
    graphql_user.save()

    create_population_comments_for_pools(
        audit_population, comment, [ALL_POOL, LCL_CX_POOL]
    )
    create_population_comments_for_pools(
        audit_population_submitted, comment, [LAIKA_POOL, ALL_POOL]
    )

    response = graphql_client.execute(
        GET_AUDITEE_AUDIT_POPULATIONS,
        variables={
            'auditId': audit.id,
        },
    )

    data = response['data']['auditeeAuditPopulations']
    opened_populations = data['open']
    submitted_populations = data['submitted']

    assert opened_populations[0]['commentsCounter'] == 2
    assert submitted_populations[0]['commentsCounter'] == 2


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
@pytest.mark.skipif(
    True,
    reason='''We can not test this because sqlite3
                                    does not support regex operations''',
)
def test_get_auditee_audit_populations_comments_public_pool(
    graphql_client,
    audit,
    audit_population,
    audit_population_submitted,
    comment,
):
    create_population_comments_for_pools(
        audit_population, comment, [ALL_POOL, LCL_CX_POOL]
    )
    create_population_comments_for_pools(
        audit_population_submitted, comment, [LAIKA_POOL, LCL_POOL]
    )

    response = graphql_client.execute(
        GET_AUDITEE_AUDIT_POPULATIONS,
        variables={
            'auditId': audit.id,
        },
    )

    data = response['data']['auditeeAuditPopulations']
    opened_populations = data['open']
    submitted_populations = data['submitted']

    assert opened_populations[0]['commentsCounter'] == 1
    assert submitted_populations[0]['commentsCounter'] == 1


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
@pytest.mark.skipif(
    True,
    reason='''We can not test this because sqlite3
                                    does not support regex operations''',
)
def test_get_auditee_audit_populations_submitted_sort(
    graphql_client,
    audit,
):
    args = {
        'audit': audit,
        'name': 'Name test 2',
        'instructions': 'Instructions test',
        'status': 'submitted',
        'description': 'description test',
    }
    AuditPopulation.objects.bulk_create(
        [
            AuditPopulation(**{**args, 'display_id': 'POP 1', 'status': 'accepted'}),
            AuditPopulation(**{**args, 'display_id': 'POP 2', 'status': 'submitted'}),
            AuditPopulation(**{**args, 'display_id': 'POP 3', 'status': 'submitted'}),
        ]
    )

    response = graphql_client.execute(
        GET_AUDITEE_AUDIT_POPULATIONS,
        variables={
            'auditId': audit.id,
        },
    )
    data = response['data']['auditeeAuditPopulations']
    submitted_populations = data['submitted']
    statuses = list(map(lambda pop: pop.status, submitted_populations))

    assert statuses == ['submitted', 'submitted', 'accepted']


@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_update_population_status(
    graphql_client, audit_soc2_type2, audit_population_submitted
):
    assert audit_population_submitted.times_moved_back_to_open == 0

    graphql_client.execute(
        UPDATE_POPULATION,
        variables={
            'input': {
                'auditId': audit_soc2_type2.id,
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
def test_update_population_general_field(
    graphql_client, audit_soc2_type2, audit_population_submitted
):
    new_description = 'Testing a new description'
    graphql_client.execute(
        UPDATE_POPULATION,
        variables={
            'input': {
                'auditId': audit_soc2_type2.id,
                'populationId': audit_population_submitted.id,
                'fields': [{'field': 'description', 'value': new_description}],
            }
        },
    )

    updated_population = AuditPopulation.objects.get(id=audit_population_submitted.id)

    assert updated_population.description == new_description


@pytest.mark.parametrize('data_length, with_pagination', [(2, True), (3, False)])
@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_population_data_paginated(
    graphql_client,
    audit_population,
    data_length,
    with_pagination,
    population_data_sample,
):
    response = graphql_client.execute(
        AUDITEE_POPULATION_DATA,
        variables={
            "auditId": audit_population.audit.id,
            "populationId": audit_population.id,
            "pagination": {"page": 1, "pageSize": 2} if with_pagination else None,
        },
    )
    pop_data = response['data']['auditeePopulationData']
    data = pop_data['populationData']
    pagination = pop_data['pagination']

    assert len(data) == data_length
    if with_pagination:
        assert pagination['page'] == 1
        assert pagination['pages'] == 2
    else:
        assert not pagination


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_population_data_counter(
    graphql_client, audit_soc2_type2, audit_population, population_data
):
    response = graphql_client.execute(
        GET_AUDITEE_AUDIT_POPULATION,
        variables={'auditId': audit_soc2_type2.id, 'populationId': audit_population.id},
    )

    data = response['data']
    assert len(data) == 1
    assert data['auditeeAuditPopulation']['populationDataCounter'] == 1


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_population_data_counter_zero_value(
    graphql_client,
    audit_soc2_type2,
    audit_population,
):
    response = graphql_client.execute(
        GET_AUDITEE_AUDIT_POPULATION,
        variables={'auditId': audit_soc2_type2.id, 'populationId': audit_population.id},
    )

    data = response['data']
    assert len(data) == 1
    assert data['auditeeAuditPopulation']['populationDataCounter'] == 0

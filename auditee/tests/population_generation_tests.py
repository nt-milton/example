import pytest

from auditee.tests.mutations import (
    CREATE_LAIKA_SOURCE_POPULATION,
    CREATE_MANUAL_SOURCE_POPULATION,
    UPLOAD_POPULATION_FILE,
)
from auditee.tests.population_tests import (
    population_1_file_path,
    population_1_with_instructions_file_path,
)
from auditee.tests.queries import (
    AUDITEE_POPULATION_LAIKA_SOURCE_DATA_EXISTS,
    GET_AUDITEE_AUDIT_POPULATION,
)
from laika.tests.utils import file_to_base64
from population.constants import PEOPLE_SOURCE, POPULATION_SOURCE_DICT
from population.models import AuditPopulation, PopulationCompletenessAccuracy


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_people_population_data_source_exists_missing_data(
    graphql_client,
    graphql_organization,
    graphql_user,
    audit_population,
    audit,
    laika_source_population_and_samples_feature_flag,
):
    audit_population.default_source = 'People'
    audit_population.save()

    response = graphql_client.execute(
        AUDITEE_POPULATION_LAIKA_SOURCE_DATA_EXISTS,
        variables=dict(
            auditId=audit_population.audit.id, populationId=audit_population.id
        ),
    )
    assert (
        response['data']['auditeeAuditPopulation']['laikaSourceDataDetected']
        == '{"People": false}'
    )


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_people_population_data_source_exists_no_feature_flag(
    graphql_client,
    graphql_organization,
    graphql_user,
    audit_population,
    audit,
):
    audit_population.default_source = 'People'
    audit_population.save()

    response = graphql_client.execute(
        AUDITEE_POPULATION_LAIKA_SOURCE_DATA_EXISTS,
        variables=dict(
            auditId=audit_population.audit.id, populationId=audit_population.id
        ),
    )
    assert (
        response['data']['auditeeAuditPopulation']['laikaSourceDataDetected']
        == '{"People": false}'
    )


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_people_population_data_source_exists_invalid_default_source(
    graphql_client,
    graphql_organization,
    graphql_user,
    audit_population,
    audit,
    laika_source_population_and_samples_feature_flag,
):
    audit_population.default_source = 'Vendors'
    audit_population.save()

    response = graphql_client.execute(
        AUDITEE_POPULATION_LAIKA_SOURCE_DATA_EXISTS,
        variables=dict(
            auditId=audit_population.audit.id, populationId=audit_population.id
        ),
    )
    assert (
        response['data']['auditeeAuditPopulation']['laikaSourceDataDetected']
        == '{"Vendors": false}'
    )


@pytest.mark.functional(permissions=['population.add_auditpopulation'])
def test_create_population_from_laika_source(
    graphql_client,
    graphql_organization,
    laika_source_user,
    audit,
    audit_population,
    graphql_user_valid_data,
    completeness_accuracy,
):
    audit_population.default_source = 'People'
    audit_population.save()

    response = graphql_client.execute(
        CREATE_LAIKA_SOURCE_POPULATION,
        variables={
            'input': {
                'auditId': audit_population.audit.id,
                'populationId': audit_population.id,
                'source': PEOPLE_SOURCE,
            }
        },
    )

    laika_source_population = response['data']['createAuditeeLaikaSourcePopulation'][
        'laikaSourcePopulation'
    ]

    population_data = laika_source_population['populationData']
    errors = laika_source_population['errors']
    updated_audit_population = AuditPopulation.objects.get(id=audit_population.id)
    completeness_accuracy = PopulationCompletenessAccuracy.objects.all()

    assert len(population_data) == 2
    assert (
        updated_audit_population.selected_source
        == POPULATION_SOURCE_DICT['laika_source']
    )
    assert updated_audit_population.data_file_name == ''
    assert not updated_audit_population.data_file
    assert updated_audit_population.configuration_saved is None
    assert updated_audit_population.laika_source_configuration is None
    assert updated_audit_population.configuration_filters is None
    assert not errors
    assert updated_audit_population.selected_default_source == PEOPLE_SOURCE
    assert completeness_accuracy.count() == 0


@pytest.mark.functional(permissions=['population.add_auditpopulation'])
def test_create_population_from_laika_source_missing_data(
    graphql_client, graphql_organization, laika_source_user, audit, audit_population
):
    audit_population.default_source = 'People'
    audit_population.save()

    response = graphql_client.execute(
        CREATE_LAIKA_SOURCE_POPULATION,
        variables={
            'input': {
                'auditId': audit_population.audit.id,
                'populationId': audit_population.id,
                'source': PEOPLE_SOURCE,
            }
        },
    )

    laika_source_population = response['data']['createAuditeeLaikaSourcePopulation'][
        'laikaSourcePopulation'
    ]

    population_data = laika_source_population['populationData']
    errors = laika_source_population['errors']
    assert len(population_data) == 0
    assert errors is True


@pytest.mark.functional(permissions=['population.add_auditpopulation'])
def test_create_population_from_laika_source_pop_2_missing_data(
    graphql_client,
    graphql_organization,
    laika_source_user_terminated,
    audit,
    audit_population_people_source_pop_2,
):
    laika_source_user_terminated.title = ''
    laika_source_user_terminated.save()

    response = graphql_client.execute(
        CREATE_LAIKA_SOURCE_POPULATION,
        variables={
            'input': {
                'auditId': audit_population_people_source_pop_2.audit.id,
                'populationId': audit_population_people_source_pop_2.id,
                'source': PEOPLE_SOURCE,
            }
        },
    )

    laika_source_population = response['data']['createAuditeeLaikaSourcePopulation'][
        'laikaSourcePopulation'
    ]

    population_data = laika_source_population['populationData']
    errors = laika_source_population['errors']

    assert len(population_data) == 0
    assert errors is True


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_correct_column_types_laika_source_population(
    graphql_client,
    graphql_organization,
    graphql_user,
    audit,
    audit_population_people_source_pop_2,
):
    response = graphql_client.execute(
        GET_AUDITEE_AUDIT_POPULATION,
        variables={
            'auditId': audit_population_people_source_pop_2.audit.id,
            'populationId': audit_population_people_source_pop_2.id,
        },
    )

    column_types = response['data']['auditeeAuditPopulation']['columnTypes']

    assert (
        column_types
        == '{"Name": "TEXT", "Email": "USER", "Title": "TEXT", "End Date": "DATE",'
        ' "Employment Type": "TEXT"}'
    )


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_correct_column_types_manual_population(
    graphql_client,
    graphql_organization,
    graphql_user,
    audit,
    audit_population,
):
    response = graphql_client.execute(
        GET_AUDITEE_AUDIT_POPULATION,
        variables={
            'auditId': audit_population.audit.id,
            'populationId': audit_population.id,
        },
    )

    column_types = response['data']['auditeeAuditPopulation']['columnTypes']
    assert (
        column_types
        == '{"Employee Name": "TEXT", "Employee Email": "USER", "Job Title": "TEXT",'
        ' "Hire Date": "DATE", "Contractor": "BOOLEAN", "Location": "TEXT"}'
    )


@pytest.mark.parametrize(
    'file_path, population_data_size',
    [(population_1_file_path, 1), (population_1_with_instructions_file_path, 2)],
)
@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_create_population_from_manual_source(
    graphql_client, audit_soc2_type2, audit_population, file_path, population_data_size
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
    graphql_client.execute(
        UPLOAD_POPULATION_FILE, variables=upload_population_file_input
    )

    response = graphql_client.execute(
        CREATE_MANUAL_SOURCE_POPULATION,
        variables={
            'input': {
                'auditId': audit_population.audit.id,
                'populationId': audit_population.id,
            }
        },
    )

    manual_source_population = response['data']['createAuditeeManualSourcePopulation'][
        'manualSourcePopulation'
    ]

    population_data = manual_source_population['populationData']
    updated_audit_population = AuditPopulation.objects.get(id=audit_population.id)

    assert len(population_data) == population_data_size
    assert updated_audit_population.selected_source == POPULATION_SOURCE_DICT['manual']
    assert updated_audit_population.configuration_saved is None
    assert updated_audit_population.laika_source_configuration is None
    assert updated_audit_population.configuration_filters is None
    assert updated_audit_population.selected_default_source is None


@pytest.mark.functional(permissions=['population.add_auditpopulation'])
def test_create_population_from_laika_source_mixed_data_pop_1(
    graphql_client,
    graphql_organization,
    laika_source_user_terminated,
    audit_population,
    graphql_user_valid_data,
):
    response = graphql_client.execute(
        CREATE_LAIKA_SOURCE_POPULATION,
        variables={
            'input': {
                'auditId': audit_population.audit.id,
                'populationId': audit_population.id,
                'source': PEOPLE_SOURCE,
            }
        },
    )

    laika_source_population = response['data']['createAuditeeLaikaSourcePopulation'][
        'laikaSourcePopulation'
    ]

    population_data = laika_source_population['populationData']
    errors = laika_source_population['errors']

    assert len(population_data) == 1
    assert not errors


@pytest.mark.functional(permissions=['population.add_auditpopulation'])
def test_create_population_from_laika_source_mixed_data_pop_2(
    graphql_client,
    graphql_organization,
    laika_source_user_terminated,
    audit_population_people_source_pop_2,
    graphql_user_valid_data,
):
    response = graphql_client.execute(
        CREATE_LAIKA_SOURCE_POPULATION,
        variables={
            'input': {
                'auditId': audit_population_people_source_pop_2.audit.id,
                'populationId': audit_population_people_source_pop_2.id,
                'source': PEOPLE_SOURCE,
            }
        },
    )

    laika_source_population = response['data']['createAuditeeLaikaSourcePopulation'][
        'laikaSourcePopulation'
    ]

    population_data = laika_source_population['populationData']
    errors = laika_source_population['errors']

    assert len(population_data) == 1
    assert not errors

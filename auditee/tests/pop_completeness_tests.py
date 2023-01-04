import os

import pytest
from django.core.files import File

from auditee.tests.mutations import (
    ADD_COMPLETENESS_ACCURACY,
    CREATE_LAIKA_SOURCE_COMPLETENESS_ACCURACY_FILE,
    DELETE_AUDITEE_COMPLETENESS_ACCURACY,
    UPDATE_AUDITEE_COMPLETENESS_ACCURACY,
)
from auditee.tests.queries import AUDITEE_GET_COMPLETENESS_ACCURACY
from laika.tests.utils import file_to_base64
from population.models import PopulationCompletenessAccuracy

template_seed_zip_path = 'organization/tests/resources/template_seed.zip'
template_seed_file_path = f'{os.path.dirname(__file__)}/resources/template_seed.xlsx'
pdf_file_path = f'{os.path.dirname(__file__)}/resources/test_pdf.pdf'


@pytest.mark.functional(permissions=['population.view_populationcompletenessaccuracy'])
def test_get_auditee_population_completeness_accuracy(
    graphql_client, audit_soc2_type2, completeness_accuracy
):
    response = graphql_client.execute(
        AUDITEE_GET_COMPLETENESS_ACCURACY,
        variables={
            'auditId': audit_soc2_type2.id,
            'populationId': completeness_accuracy.population.id,
        },
    )

    data = response['data']['auditeePopulationCompletenessAccuracy']

    assert len(data) == 1
    assert data[0]['name'] == 'template_seed.xlsx'


@pytest.mark.functional(permissions=['population.add_populationcompletenessaccuracy'])
def test_add_auditee_population_completeness_files(
    graphql_client,
    audit_population,
):
    response = graphql_client.execute(
        ADD_COMPLETENESS_ACCURACY,
        variables={
            'input': dict(
                auditId=audit_population.audit.id,
                populationId=audit_population.id,
                files=[
                    {'fileName': 'testfile.pdf', 'file': file_to_base64(pdf_file_path)},
                    {
                        'fileName': 'testfile2.pdf',
                        'file': file_to_base64(pdf_file_path),
                    },
                ],
            )
        },
    )

    data = response['data']['addAuditeePopulationCompletenessAccuracy']
    files = data['completenessAccuracyList']
    completeness_accuracy_files = PopulationCompletenessAccuracy.objects.filter(
        population=audit_population
    )

    assert len(files) == len(completeness_accuracy_files)


@pytest.mark.functional(permissions=['population.add_populationcompletenessaccuracy'])
def test_add_auditee_population_completeness_files_not_supported_file(
    graphql_client,
    audit_population,
):
    response = graphql_client.execute(
        ADD_COMPLETENESS_ACCURACY,
        variables={
            'input': dict(
                auditId=audit_population.audit.id,
                populationId=audit_population.id,
                files=[
                    {
                        'fileName': 'testfile2.zip',
                        'file': file_to_base64(template_seed_zip_path),
                    }
                ],
            )
        },
    )

    errors = response['errors'][0]

    assert errors['message'] == 'File type not supported'


@pytest.mark.functional(permissions=['population.add_populationcompletenessaccuracy'])
def test_add_auditee_population_completeness_files_no_more_than_5_files(
    graphql_client,
    audit_population,
):
    response = graphql_client.execute(
        ADD_COMPLETENESS_ACCURACY,
        variables={
            'input': dict(
                auditId=audit_population.audit.id,
                populationId=audit_population.id,
                files=[
                    {
                        'fileName': 'testfile1.pdf',
                        'file': file_to_base64(pdf_file_path),
                    },
                    {
                        'fileName': 'testfile2.pdf',
                        'file': file_to_base64(pdf_file_path),
                    },
                    {
                        'fileName': 'testfile3.pdf',
                        'file': file_to_base64(pdf_file_path),
                    },
                    {
                        'fileName': 'testfile4.pdf',
                        'file': file_to_base64(pdf_file_path),
                    },
                    {
                        'fileName': 'testfile5.pdf',
                        'file': file_to_base64(pdf_file_path),
                    },
                    {
                        'fileName': 'testfile6.pdf',
                        'file': file_to_base64(pdf_file_path),
                    },
                ],
            )
        },
    )

    errors = response['errors'][0]

    assert errors['message'] == 'Max number of files exceeded'


@pytest.mark.functional(permissions=['population.add_populationcompletenessaccuracy'])
def test_add_completeness_files_with_file_do_not_allow_more_than_5_files(
    graphql_client, audit_population, completeness_accuracy
):
    response = graphql_client.execute(
        ADD_COMPLETENESS_ACCURACY,
        variables={
            'input': dict(
                auditId=audit_population.audit.id,
                populationId=audit_population.id,
                files=[
                    {
                        'fileName': 'testfile1.pdf',
                        'file': file_to_base64(pdf_file_path),
                    },
                    {
                        'fileName': 'testfile2.pdf',
                        'file': file_to_base64(pdf_file_path),
                    },
                    {
                        'fileName': 'testfile3.pdf',
                        'file': file_to_base64(pdf_file_path),
                    },
                    {
                        'fileName': 'testfile4.pdf',
                        'file': file_to_base64(pdf_file_path),
                    },
                    {
                        'fileName': 'testfile5.pdf',
                        'file': file_to_base64(pdf_file_path),
                    },
                ],
            )
        },
    )

    errors = response['errors'][0]

    assert errors['message'] == 'Max number of files exceeded'


@pytest.mark.functional(permissions=['population.add_populationcompletenessaccuracy'])
def test_add_auditee_population_completeness_files_no_files_found(
    graphql_client,
    audit_population,
):
    response = graphql_client.execute(
        ADD_COMPLETENESS_ACCURACY,
        variables={
            'input': dict(
                auditId=audit_population.audit.id,
                populationId=audit_population.id,
                files=[],
            )
        },
    )

    errors = response['errors'][0]

    assert errors['message'] == 'No files found'


@pytest.mark.functional(
    permissions=['population.change_populationcompletenessaccuracy']
)
def test_update_auditee_population_completeness_file(
    graphql_client, audit_population, completeness_accuracy
):
    new_name = 'Updated name.pdf'
    graphql_client.execute(
        UPDATE_AUDITEE_COMPLETENESS_ACCURACY,
        variables={
            'input': dict(
                auditId=audit_population.audit.id,
                populationId=audit_population.id,
                id=completeness_accuracy.id,
                newName=new_name,
            )
        },
    )

    completeness_accuracy_file = PopulationCompletenessAccuracy.objects.get(
        id=completeness_accuracy.id
    )

    assert completeness_accuracy_file.name == new_name


@pytest.mark.functional(
    permissions=['population.change_populationcompletenessaccuracy']
)
def test_update_auditee_population_completeness_file_unique_name(
    graphql_client, audit_population, completeness_accuracy
):
    PopulationCompletenessAccuracy.objects.create(
        population=audit_population,
        name='new_seed.xlsx',
        file=File(open(template_seed_file_path, "rb")),
    )
    new_name = 'new_seed.xlsx'
    response = graphql_client.execute(
        UPDATE_AUDITEE_COMPLETENESS_ACCURACY,
        variables={
            'input': dict(
                auditId=audit_population.audit.id,
                populationId=audit_population.id,
                id=completeness_accuracy.id,
                newName=new_name,
            )
        },
    )
    error = response['errors'][0]
    assert error['message'] == 'This file name already exists. Use a different name.'


@pytest.mark.functional(
    permissions=['population.delete_populationcompletenessaccuracy']
)
def test_delete_auditee_population_completeness_file(
    graphql_client, audit_population, completeness_accuracy
):
    graphql_client.execute(
        DELETE_AUDITEE_COMPLETENESS_ACCURACY,
        variables={
            'input': dict(
                auditId=audit_population.audit.id,
                populationId=audit_population.id,
                id=completeness_accuracy.id,
            )
        },
    )

    completeness_accuracy_file = PopulationCompletenessAccuracy.objects.get(
        id=completeness_accuracy.id
    )

    assert completeness_accuracy_file.is_deleted


@pytest.mark.functional(permissions=['population.add_populationcompletenessaccuracy'])
def test_create_laika_source_completeness_accuracy_file(
    graphql_client, audit_population_people_source_pop_2, lo_for_account_type
):
    expected_file_name = (
        'Completeness and Accuracy -'
        f' {audit_population_people_source_pop_2.display_id}.xlsx'
    )

    graphql_client.execute(
        CREATE_LAIKA_SOURCE_COMPLETENESS_ACCURACY_FILE,
        variables={
            'input': dict(
                auditId=audit_population_people_source_pop_2.audit.id,
                populationId=audit_population_people_source_pop_2.id,
                source='People',
            )
        },
    )

    completeness_accuracy_file = PopulationCompletenessAccuracy.objects.get(
        population_id=audit_population_people_source_pop_2.id
    )

    assert completeness_accuracy_file.name == expected_file_name
    assert completeness_accuracy_file.file is not None


@pytest.mark.functional(permissions=['population.add_populationcompletenessaccuracy'])
def test_create_laika_source_completeness_accuracy_file_pop_1(
    graphql_client, audit_population, lo_for_account_type
):
    expected_file_name = (
        f'Completeness and Accuracy - {audit_population.display_id}.xlsx'
    )

    graphql_client.execute(
        CREATE_LAIKA_SOURCE_COMPLETENESS_ACCURACY_FILE,
        variables={
            'input': dict(
                auditId=audit_population.audit.id,
                populationId=audit_population.id,
                source='People',
            )
        },
    )

    completeness_accuracy_file = PopulationCompletenessAccuracy.objects.get(
        population_id=audit_population.id
    )

    assert completeness_accuracy_file.name == expected_file_name
    assert completeness_accuracy_file.file is not None

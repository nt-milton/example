import json
import os

import pytest

from auditee.tests.mutations import UPDATE_POPULATION
from auditee.tests.queries import (
    AUDITEE_POPULATION_CONFIGURATION_QUESTIONS,
    GET_AUDITEE_AUDIT_POPULATION_CONFIGURATION,
)
from population.models import PopulationData

template_seed_file_path = f'{os.path.dirname(__file__)}/resources/template_seed.xlsx'


@pytest.mark.functional(permissions=['population.change_auditpopulation'])
def test_update_population_configuration_saved(
    graphql_client,
    audit_soc2_type2,
    audit_population,
):
    configuration_saved = [
        '{"question":"Question saved", "answer_column": ["My answer"]}'
    ]

    update_population_configuration_saved_input = {
        'input': dict(
            auditId=audit_soc2_type2.id,
            populationId=audit_population.id,
            fields=[{'field': 'configuration_saved', 'jsonList': configuration_saved}],
        )
    }

    response = graphql_client.execute(
        UPDATE_POPULATION, variables=update_population_configuration_saved_input
    )
    data = response['data']['updateAuditeePopulation']['auditPopulation']
    configuration_saved_dict = json.loads(data['configurationSaved'][0])
    assert configuration_saved_dict['question'] == 'Question saved'
    assert configuration_saved_dict['answer_column'] == ["My answer"]


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_pop_config_question_empty(graphql_client, audit_population):
    audit_population.configuration_seed = None
    audit_population.save()
    response = graphql_client.execute(
        AUDITEE_POPULATION_CONFIGURATION_QUESTIONS,
        variables={
            'auditId': audit_population.audit.id,
            'populationId': audit_population.id,
        },
    )

    questions = response['data']['auditeePopulationConfigurationQuestions']
    assert len(questions) == 0


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_pop_config_questions_no_duplicates(graphql_client, audit_population):
    column = 'Job Title'
    job_title_1 = 'Stand Master'
    job_title_2 = 'Hokage'
    audit_population.configuration_seed = [
        {
            'type': 'MULTISELECT',
            'question': 'What job titles have access?',
            'answer_column': column,
        }
    ]
    audit_population.save()
    PopulationData.objects.bulk_create(
        [
            PopulationData(data={column: job_title_1}, population=audit_population),
            PopulationData(data={column: job_title_2}, population=audit_population),
            PopulationData(data={column: job_title_1}, population=audit_population),
            PopulationData(data={column: job_title_2}, population=audit_population),
        ]
    )

    response = graphql_client.execute(
        AUDITEE_POPULATION_CONFIGURATION_QUESTIONS,
        variables={
            'auditId': audit_population.audit.id,
            'populationId': audit_population.id,
        },
    )

    questions = response['data']['auditeePopulationConfigurationQuestions']
    question = questions[0]
    assert len(questions) == 1
    assert question['question'] == 'What job titles have access?'
    assert question['type'] == 'MULTISELECT'
    assert question['answers'] == [job_title_1, job_title_2]
    assert question['column'] == column


HIRE_DATE_COLUMN = 'Hire Date'
JOB_TITLE_COLUMN = 'Job Title'
JOB_TITLE_1 = 'Stand Master'
JOB_TITLE_2 = 'Hokage'

CONF_QUESTIONS = [
    {
        'type': 'DATE_RANGE',
        'question': 'What is the review period of the audit?',
        'answer_column': HIRE_DATE_COLUMN,
        'operator': 'is_between',
    },
    {
        'type': 'MULTISELECT',
        'question': 'What job titles have access?',
        'answer_column': JOB_TITLE_COLUMN,
    },
]


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_pop_config_questions(graphql_client, audit_soc2_type2, audit_population):
    as_of_date = '2022-01-05'
    audit_soc2_type2.audit_configuration = {
        'as_of_date': as_of_date,
        'trust_services_categories': ["Security"],
    }
    audit_soc2_type2.save()

    audit_population.configuration_seed = CONF_QUESTIONS
    audit_population.save()
    PopulationData.objects.bulk_create(
        [
            PopulationData(
                data={JOB_TITLE_COLUMN: JOB_TITLE_1}, population=audit_population
            ),
            PopulationData(
                data={JOB_TITLE_COLUMN: JOB_TITLE_2}, population=audit_population
            ),
            PopulationData(
                data={JOB_TITLE_COLUMN: JOB_TITLE_1}, population=audit_population
            ),
            PopulationData(
                data={JOB_TITLE_COLUMN: JOB_TITLE_2}, population=audit_population
            ),
        ]
    )

    response = graphql_client.execute(
        AUDITEE_POPULATION_CONFIGURATION_QUESTIONS,
        variables={
            'auditId': audit_population.audit.id,
            'populationId': audit_population.id,
        },
    )

    questions = response['data']['auditeePopulationConfigurationQuestions']

    assert len(questions) == 2
    question = questions[0]
    assert question['question'] == 'What is the review period of the audit?'
    assert question['type'] == 'DATE_RANGE'
    assert question['answers'] == [as_of_date]
    assert question['column'] == HIRE_DATE_COLUMN
    assert question['operator'] == 'is_between'

    question = questions[1]
    assert question['question'] == 'What job titles have access?'
    assert question['type'] == 'MULTISELECT'
    assert question['answers'] == [JOB_TITLE_1, JOB_TITLE_2]
    assert question['column'] == JOB_TITLE_COLUMN
    assert question['operator'] is None


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_auditee_audit_population_configuration_question_and_answers(
    graphql_client, audit_soc2_type2, audit_population
):
    response = graphql_client.execute(
        GET_AUDITEE_AUDIT_POPULATION_CONFIGURATION,
        variables={'auditId': audit_soc2_type2.id, 'populationId': audit_population.id},
    )

    data = response['data']['auditeeAuditPopulation']
    configuration_seed_dict = json.loads(data['configurationSeed'][0])
    assert configuration_seed_dict['question'] == 'Configuration question test'
    assert configuration_seed_dict['answer_column'] == ["DEMO", "TEST", "NAME"]
    assert configuration_seed_dict['type'] == 'MULTISELECT'


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_pop_laika_source_config_questions(
    graphql_client, audit_soc2_type2, audit_laika_source_population
):
    audit_laika_source_population.laika_source_configuration = CONF_QUESTIONS
    audit_laika_source_population.save()
    PopulationData.objects.bulk_create(
        [
            PopulationData(
                data={JOB_TITLE_COLUMN: JOB_TITLE_1},
                population=audit_laika_source_population,
            ),
            PopulationData(
                data={JOB_TITLE_COLUMN: JOB_TITLE_2},
                population=audit_laika_source_population,
            ),
            PopulationData(
                data={JOB_TITLE_COLUMN: JOB_TITLE_1},
                population=audit_laika_source_population,
            ),
            PopulationData(
                data={JOB_TITLE_COLUMN: JOB_TITLE_2},
                population=audit_laika_source_population,
            ),
        ]
    )

    response = graphql_client.execute(
        AUDITEE_POPULATION_CONFIGURATION_QUESTIONS,
        variables={
            'auditId': audit_laika_source_population.audit.id,
            'populationId': audit_laika_source_population.id,
        },
    )

    questions = response['data']['auditeePopulationConfigurationQuestions']
    assert len(questions) == 2
    question = questions[0]
    assert question['question'] == 'What is the review period of the audit?'
    assert question['type'] == 'DATE_RANGE'
    assert question['answers'] == ["2022-08-18,2022-08-20"]
    assert question['column'] == HIRE_DATE_COLUMN
    assert question['operator'] == 'is_between'

    question = questions[1]
    assert question['question'] == 'What job titles have access?'
    assert question['type'] == 'MULTISELECT'
    assert question['answers'] == [JOB_TITLE_1, JOB_TITLE_2]
    assert question['column'] == JOB_TITLE_COLUMN
    assert question['operator'] is None

import os

import pytest
from django.core.files import File

from audit.constants import AUDIT_TYPES
from audit.tests.factory import create_audit
from fieldwork.models import Criteria, Evidence, Requirement, Test
from population.models import AuditPopulation
from seeder.admin import FieldworkSeed
from seeder.constants import DONE
from seeder.models import Seed

FILE_PATH = os.path.dirname(__file__)
fieldwork_seed_file_path = f'{FILE_PATH}/resources/fieldwork_seed.zip'
fieldwork_seed_criteria_file_path = f'{FILE_PATH}/resources/fieldwork_seed2.zip'
fieldwork_seed_test_file_path = f'{FILE_PATH}/resources/fieldwork_seed_tests.zip'
population_fieldwork_seed_file_path = (
    f'{FILE_PATH}/resources/population_fieldwork_seed.zip'
)
population_fieldwork_seed_with_errors_file_path = (
    f'{FILE_PATH}/resources/population_fieldwork_seed_with_errors.zip'
)


@pytest.fixture
def audit2(graphql_organization, graphql_audit_firm):
    return create_audit(
        organization=graphql_organization,
        name='Second Audit',
        audit_firm=graphql_audit_firm,
        audit_type=AUDIT_TYPES[1],
        is_completed=True,
    )


def seed_fieldwork_file(file_path, audit_to_seed):
    file_to_seed = File(open(file_path, "rb"))
    seed = FieldworkSeed.objects.create(audit=audit_to_seed, seed_file=file_to_seed)
    return Seed.objects.get(id=seed.id)


@pytest.mark.functional
def test_seed_fieldwork_task(audit):
    updated_seed = seed_fieldwork_file(fieldwork_seed_file_path, audit)
    requirements_count = Requirement.objects.all().count()
    evidence_count = Evidence.objects.all().count()

    assert updated_seed.status == DONE
    assert requirements_count == 64
    assert evidence_count == 73


@pytest.mark.functional
def test_seed_fieldwork_criteria(audit):
    expected_requirements = ['LCL-1', 'LCL-2']
    updated_seed = seed_fieldwork_file(fieldwork_seed_criteria_file_path, audit)

    criteria = Criteria.objects.all()

    assert updated_seed.status == DONE
    assert criteria.count() == 3

    for c in criteria:
        if c.display_id == 'CC 1.2':
            assert c.requirements.exists() is False

        for r in c.requirements.all():
            assert r.display_id in expected_requirements
        assert c.audit == audit


@pytest.mark.functional
def test_seed_fieldwork_criteria_on_two_audits(audit, audit2):
    # Seeding for first audit
    first_seed = seed_fieldwork_file(fieldwork_seed_criteria_file_path, audit)

    assert first_seed.status == DONE

    # Seeding for second audit
    second_seed = seed_fieldwork_file(fieldwork_seed_criteria_file_path, audit2)
    criteria = Criteria.objects.all()

    assert second_seed.status == DONE

    assert criteria.count() == 6

    all_criteria_requirements_count = 0
    for c in criteria:
        all_criteria_requirements_count += c.requirements.count()

    assert all_criteria_requirements_count == 6


@pytest.mark.functional
def test_seed_fieldwork_tests(audit):
    expected_requirements = ['LCL-1', 'LCL-2']
    updated_seed = seed_fieldwork_file(fieldwork_seed_test_file_path, audit)
    tests = Test.objects.all()

    assert updated_seed.status == DONE
    assert tests.count() == 3

    for t in tests:
        assert t.requirement.display_id in expected_requirements


@pytest.mark.functional
def test_seed_fieldwork_populations_seed_multiple_questions(audit):
    question = 'What job titles support the in-scope services?'
    answer_type = 'MULTISELECT'
    answer_column = ['Job Title', 'Name']
    updated_seed = seed_fieldwork_file(population_fieldwork_seed_file_path, audit)
    populations = AuditPopulation.objects.all()

    assert updated_seed.status == DONE
    assert populations.count() == 7

    first_pop = populations.first()
    configuration_seed = first_pop.configuration_seed
    assert len(configuration_seed) == 3
    assert configuration_seed[0]['question'] == question
    assert configuration_seed[0]['type'] == answer_type
    assert configuration_seed[0]['answer_column'] == answer_column


@pytest.mark.functional
def test_seed_laika_source_configuration_questions(audit):
    question = 'What job titles support the in-scope services?'
    answer_type = 'MULTISELECT'
    answer_column = ['Job Title', 'Name']
    updated_seed = seed_fieldwork_file(population_fieldwork_seed_file_path, audit)
    populations = AuditPopulation.objects.all()

    assert updated_seed.status == DONE
    assert populations.count() == 7

    first_pop = populations.first()
    configuration_questions = first_pop.laika_source_configuration
    assert len(configuration_questions) == 3
    assert configuration_questions[0]['question'] == question
    assert configuration_questions[0]['type'] == answer_type
    assert configuration_questions[0]['answer_column'] == answer_column


@pytest.mark.functional
def test_seed_fieldwork_populations_seed_one_question(audit):
    question = 'What job titles have access?'
    answer_type = 'MULTISELECT'
    answer_column = ['Job Title', 'Name']
    seed_fieldwork_file(population_fieldwork_seed_file_path, audit)

    population = AuditPopulation.objects.get(id=2)
    configuration_seed = population.configuration_seed
    assert len(configuration_seed) == 1
    assert configuration_seed[0]['question'] == question
    assert configuration_seed[0]['type'] == answer_type
    assert configuration_seed[0]['answer_column'] == answer_column


@pytest.mark.functional
def test_seed_fieldwork_populations_error(audit):
    seed = seed_fieldwork_file(population_fieldwork_seed_with_errors_file_path, audit)
    assert 'Invalid Json format' in seed.status_detail


@pytest.mark.skipif(True, reason='TDD FZ-2235')
@pytest.mark.functional
def test_seed_population_with_non_sample_ers(audit):
    seed = seed_fieldwork_file(population_fieldwork_seed_file_path, audit)

    pop_3 = AuditPopulation.objects.get(display_id='POP-3')
    pop_3_ers = pop_3.evidence_request.all()
    assert pop_3_ers.count() == 1
    assert pop_3_ers.first().display_id == 'ER-34'
    assert (
        'Unable to link evidence request to POP-3 evidence request ER-87 '
        'not found or is not of sample type'
        in seed.status_detail
    )


@pytest.mark.functional
def test_seed_fieldwork_task_exclude_in_report(audit):
    seed = seed_fieldwork_file(fieldwork_seed_file_path, audit)
    requirements_count = Requirement.objects.count()

    assert seed.status == DONE
    assert requirements_count == 64

    filtered_requirements = Requirement.objects.filter(exclude_in_report=True)
    assert len(filtered_requirements) == 2

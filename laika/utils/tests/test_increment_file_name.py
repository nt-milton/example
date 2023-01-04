import pytest
from django.core.files import File

from laika.utils.increment_file_name import increment_file_name
from population.models import PopulationCompletenessAccuracy

TEMPLATE_SEED_FILE_PATH = 'auditee/tests/resources/template_seed.xlsx'

FILE_NAME = 'test_filename.xlsx'


@pytest.mark.functional
def test_no_file_with_same_name():
    new_file_name = increment_file_name(PopulationCompletenessAccuracy, FILE_NAME, {})

    assert FILE_NAME == new_file_name


@pytest.mark.functional
def test_increment_file_name_once(audit_population):
    PopulationCompletenessAccuracy.objects.create(
        population=audit_population,
        name=FILE_NAME,
        file=File(open(TEMPLATE_SEED_FILE_PATH, "rb")),
    )
    new_file_name = increment_file_name(
        PopulationCompletenessAccuracy, FILE_NAME, {'population': audit_population}
    )

    assert new_file_name == 'test_filename(1).xlsx'


@pytest.mark.functional
def test_increment_file_name_three_times(audit_population):
    file = File(open(TEMPLATE_SEED_FILE_PATH, "rb"))
    PopulationCompletenessAccuracy.objects.bulk_create(
        [
            PopulationCompletenessAccuracy(
                population=audit_population, name=FILE_NAME, file=file
            ),
            PopulationCompletenessAccuracy(
                population=audit_population, name='test_filename(1).xlsx', file=file
            ),
            PopulationCompletenessAccuracy(
                population=audit_population, name='test_filename(2).xlsx', file=file
            ),
        ]
    )

    new_file_name = increment_file_name(
        PopulationCompletenessAccuracy, FILE_NAME, {'population': audit_population}
    )

    assert new_file_name == 'test_filename(3).xlsx'

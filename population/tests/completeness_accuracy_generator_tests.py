import pytest

from population.completeness_accuracy.completeness_accuracy_generator import (
    CompletenessAccuracyGeneratorFactory,
    PeopleCompletenessAccuracyFileGenerator,
)
from population.constants import POPULATION_DEFAULT_SOURCE_DICT
from population.models import PopulationCompletenessAccuracy


@pytest.mark.django_db
def test_create_laika_source_people_completeness_accuracy(
    audit_population, lo_for_account_type
):
    expected_file_name = (
        f'Completeness and Accuracy - {audit_population.display_id}.xlsx'
    )
    audit_population.selected_source = 'laika_source'
    audit_population.save()

    file_generator = PeopleCompletenessAccuracyFileGenerator(
        population=audit_population
    )
    file_generator.create_population_completeness_accuracy()

    population_completeness_accuracy = PopulationCompletenessAccuracy.objects.get(
        population=audit_population, name=expected_file_name
    )

    assert population_completeness_accuracy.name == expected_file_name
    assert population_completeness_accuracy.file is not None


@pytest.mark.django_db
def test_create_laika_source_people_completeness_accuracy_pop_2(
    audit_population_people_source_pop_2, lo_for_account_type
):
    expected_file_name = (
        'Completeness and Accuracy -'
        f' {audit_population_people_source_pop_2.display_id}.xlsx'
    )
    source = POPULATION_DEFAULT_SOURCE_DICT['People']

    completeness_accuracy_generator = (
        CompletenessAccuracyGeneratorFactory.get_completeness_accuracy_generator(
            source, audit_population_people_source_pop_2
        )
    )

    assert isinstance(
        completeness_accuracy_generator, PeopleCompletenessAccuracyFileGenerator
    )

    completeness_accuracy_generator.create_population_completeness_accuracy()

    population_completeness_accuracy = PopulationCompletenessAccuracy.objects.get(
        population=audit_population_people_source_pop_2, name=expected_file_name
    )
    assert population_completeness_accuracy.name == expected_file_name
    assert population_completeness_accuracy.file is not None

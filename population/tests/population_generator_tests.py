import pytest

from population.constants import POPULATION_DEFAULT_SOURCE_DICT
from population.population_builder.population_generator import get_population_generator


@pytest.mark.django_db
def test_laika_source_data_exists_people_missing_data(
    graphql_user, audit_population, laika_source_user
):
    population_generator = get_population_generator(
        POPULATION_DEFAULT_SOURCE_DICT['People']
    )

    data_exists = population_generator(audit_population).laika_source_data_exists()

    assert data_exists is False


@pytest.mark.django_db
def test_laika_source_data_exists_people(laika_source_user, audit_population):
    population_generator = get_population_generator(
        POPULATION_DEFAULT_SOURCE_DICT['People']
    )

    data_exists = population_generator(audit_population).laika_source_data_exists()

    assert data_exists is True


@pytest.mark.django_db
def test_laika_source_people_create_population_with_errors(
    audit_population, graphql_user, laika_source_user
):
    population_generator = get_population_generator(
        POPULATION_DEFAULT_SOURCE_DICT['People']
    )
    population_data, errors = population_generator(
        audit_population
    ).generate_population_rows()
    assert len(population_data) == 1
    assert len(errors) == 1


@pytest.mark.django_db
def test_laika_source_people_create_population(
    audit_population, graphql_user_valid_data, laika_source_user
):
    population_generator = get_population_generator(
        POPULATION_DEFAULT_SOURCE_DICT['People']
    )
    population_data, errors = population_generator(
        audit_population
    ).generate_population_rows()
    assert len(population_data) == 2
    assert not errors


@pytest.mark.django_db
def test_laika_source_data_exists_people_empty_values(
    graphql_user_valid_data, audit_population, laika_source_user_invalid_data
):
    population_generator = get_population_generator(
        POPULATION_DEFAULT_SOURCE_DICT['People']
    )

    data_exists = population_generator(audit_population).laika_source_data_exists()

    assert data_exists is False

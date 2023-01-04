from audit.constants import LAIKA_SOURCE_POPULATION_AND_SAMPLES_FEATURE_FLAG
from feature.models import Flag
from population.constants import POPULATION_DEFAULT_SOURCE_DICT
from population.population_builder.population_generator import get_population_generator


def get_data_detected(audit_population, source):
    is_laika_source_population_and_samples_feature_flag_enabled = (
        Flag.is_flag_enabled_for_organization(
            flag_name=LAIKA_SOURCE_POPULATION_AND_SAMPLES_FEATURE_FLAG,
            organization=audit_population.audit.organization,
        )
    )

    if (
        not is_laika_source_population_and_samples_feature_flag_enabled
        or not POPULATION_DEFAULT_SOURCE_DICT.get(source)
    ):
        return False

    population_generator = get_population_generator(source)
    return population_generator(audit_population).laika_source_data_exists()

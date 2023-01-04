from django.db.models import Q
from django.db.models.query import QuerySet

from audit.utils.incredible_filter import get_incredible_filter
from auditee.utils import get_order_by
from fieldwork.utils import get_display_id_order_annotation, get_pagination_info
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.paginator import get_paginated_result
from population.constants import POPULATION_SOURCE_DICT, POPULATION_STATUS_DICT
from population.models import (
    AuditPopulation,
    PopulationCompletenessAccuracy,
    PopulationData,
    Sample,
)
from population.population_builder.schemas import (
    POPULATION_LAIKA_SOURCE_SCHEMAS,
    POPULATION_SCHEMAS,
)
from population.types import AuditPopulationsType, PopulationDataResponseType


def get_audit_populations_by_audit_id(audit_id: str) -> AuditPopulationsType:
    order_annotate = {
        'display_id_sort': get_display_id_order_annotation(preffix='POP-')
    }

    open = (
        AuditPopulation.objects.filter(
            audit__id=audit_id, status=POPULATION_STATUS_DICT['Open']
        )
        .annotate(**order_annotate)
        .order_by('display_id_sort')
    )

    submitted = (
        AuditPopulation.objects.filter(
            Q(status=POPULATION_STATUS_DICT['Accepted'])
            | Q(status=POPULATION_STATUS_DICT['Submitted'])
        )
        .filter(audit__id=audit_id)
        .annotate(**order_annotate)
        .order_by('-status', 'display_id_sort')
    )

    return AuditPopulationsType(open=open, submitted=submitted)


def get_completeness_and_accuracy_files(
    audit_id: str, population_id: str
) -> QuerySet[PopulationCompletenessAccuracy]:
    audit_population = AuditPopulation.objects.get(audit__id=audit_id, id=population_id)
    return PopulationCompletenessAccuracy.objects.filter(
        population=audit_population, is_deleted=False
    )


def get_population_data(population_id, kwargs):
    data = AuditPopulation.objects.values('display_id', 'selected_source').get(
        id=population_id
    )
    column_types = get_column_types(data['display_id'], data['selected_source'])
    default_order_by = list(column_types.keys())[0]
    pagination, page, page_size = get_pagination_info(kwargs)
    order_by = get_order_by(kwargs, 'data__', default_order_by)
    filters = get_incredible_filter(kwargs, 'data__')
    is_sample = kwargs.get('is_sample')
    sample_filter = {'is_sample': True} if is_sample else {}

    search_field = get_population_schema(data['selected_source'])[
        data['display_id']
    ].search_field
    search_criteria = kwargs.get('search_criteria')
    search = (
        {f'data__{search_field}__icontains': search_criteria} if search_criteria else {}
    )

    population_data = (
        PopulationData.objects.filter(population_id=population_id)
        .filter(filters)
        .filter(**sample_filter)
        .filter(**search)
        .order_by(order_by)
    )

    if not pagination:
        return PopulationDataResponseType(population_data=population_data)

    paginated_result = get_paginated_result(population_data, page_size, page)

    return PopulationDataResponseType(
        population_data=paginated_result.get('data'),
        pagination=exclude_dict_keys(paginated_result, ['data']),
    )


def reset_population_data(audit_population, selected_source):
    if selected_source == POPULATION_SOURCE_DICT['laika_source']:
        if audit_population.data_file:
            audit_population.data_file.delete()
        audit_population.data_file_name = ''
    PopulationCompletenessAccuracy.objects.filter(population=audit_population).delete()
    audit_population.configuration_saved = None
    audit_population.configuration_filters = None
    audit_population.selected_default_source = None
    audit_population.save()
    PopulationData.objects.filter(population=audit_population).delete()


def get_population_schema(selected_source: str):
    return (
        POPULATION_LAIKA_SOURCE_SCHEMAS
        if selected_source == POPULATION_SOURCE_DICT['laika_source']
        else POPULATION_SCHEMAS
    )


def get_column_types(display_id, selected_source):
    schemas = get_population_schema(selected_source)
    population_schema = schemas[display_id]
    return {field.name: field.OPERATOR_TYPE for field in population_schema.fields}


def set_sample_name(sample: Sample):
    if sample.population_data:
        data = sample.population_data.data
        search_field = POPULATION_SCHEMAS[
            sample.population_data.population.display_id
        ].search_field
        sample.name = data[search_field]
        sample.save()

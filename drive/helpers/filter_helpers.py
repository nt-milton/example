from django.db.models import Q

from laika.utils.order_by import get_order_query


def get_document_filters(selected_filters: dict):
    filters = Q()

    owner_ids = selected_filters.get('owner', [])
    if owner_ids:
        filters &= Q(owner__id__in=owner_ids)

    types = selected_filters.get('type', [])
    if types:
        filters &= Q(evidence__type__in=types)

    id = selected_filters.get('id', [])
    if id:
        filters &= Q(evidence__id__in=id)

    tags = selected_filters.get('tags', [])
    if tags:
        filters &= Q(evidence__tags__in=tags)

    return filters


FILTER_MAPPER = {
    'name': 'evidence__name',
    'owner': 'owner__first_name',
    'type': 'evidence__type',
    'updated_at': 'evidence__updated_at',
    'created_at': 'evidence__created_at',
}


def build_drive_order_by_clause(**kwargs):
    order_by = kwargs.get('order_by', {'field': 'updated_at', 'order': 'descend'})

    field = order_by.get('field', 'updated_at')
    order = order_by.get('order')
    mapped_field_query = FILTER_MAPPER.get(field, 'evidence__updated_at')

    order_query = get_order_query(mapped_field_query, order)
    return order_query

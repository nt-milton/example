from django.db.models import Q

from laika.utils.query_builder import get_incredible_filter_query


def get_incredible_filter(kwargs, prefix=''):
    filters = kwargs.get('filters', [])
    filter_query = Q()
    for filter in filters:
        field = f'{prefix}{filter.get("field")}'
        incredible_filter = get_incredible_filter_query(
            field=field,
            value=filter.get('value'),
            operator=filter.get('operator'),
            attribute_type=filter.get('type'),
        )
        filter_query.add(incredible_filter, Q.AND)
    return filter_query

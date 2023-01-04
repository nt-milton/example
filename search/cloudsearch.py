import dataclasses
import json
import logging
from datetime import datetime
from typing import Any, List

import boto3

from laika.settings import AWS_CLOUD_SEARCH_URL, AWS_REGION
from search.indexing.types import IndexRecord
from search.models import Index

logger = logging.getLogger(__name__)

cloudsearch = boto3.client(
    'cloudsearchdomain', region_name=AWS_REGION, endpoint_url=AWS_CLOUD_SEARCH_URL
)
is_cloudsearch_enabled = True if AWS_CLOUD_SEARCH_URL else False


def _upload_documents_to_cloudsearch(records: List[Any]):
    if not is_cloudsearch_enabled:
        logger.info('Cloudsearch is not enabled yet for this environment.')
        return
    try:
        payload = json.dumps(records)
        response = cloudsearch.upload_documents(
            documents=str.encode(payload), contentType='application/json'
        )
        return response
    except Exception as e:
        logger.error(f'Error trying to index documents {e}')


def _build_term_filter(field, value):
    return f'(term field={field} \'{value}\')'


def _field_types_query(field_types: List[str]):
    if not field_types:
        return ''
    types_query = ' '.join(f'type:\'{field_type}\'' for field_type in field_types)
    return f'(or {types_query})'


def _build_filter_query(organization_id, include_draft: bool, field_types: List[str]):
    organization_query = _build_term_filter('organization_id', organization_id)
    include_draft_query = '' if include_draft else _build_term_filter('is_draft', '0')
    field_types_query = _field_types_query(field_types)
    return f'(and {organization_query} {include_draft_query} {field_types_query})'


def _parse_cloudsearch_search_response(response):
    records = []
    records_by_type = {}
    hits = response.get('hits').get('hit', [])
    for hit in hits:
        hit_type, *hit_id = hit.get('id').split('-')
        hit_id = '-'.join(hit_id)
        records.append((hit_type, hit_id))
        records_by_type[hit_type] = records_by_type.get(hit_type, [])
        records_by_type[hit_type].append(hit_id)
    return records, records_by_type


def _get_fields_priority():
    return (
        '{"fields":["title^4", "main_content^3", "secondary_content^2", "category^1"]}'
    )


def cloudsearch_search(
    search_criteria: str,
    organization_id: str,
    field_types: List[str],
    records_count: int,
    include_draft=False,
):
    field_types = field_types if field_types else []
    if not is_cloudsearch_enabled:
        logger.info('Cloudsearch is not enabled yet for this environment.')
        return
    try:
        response = cloudsearch.search(
            query=search_criteria,
            queryParser='lucene',
            queryOptions=_get_fields_priority(),
            filterQuery=_build_filter_query(
                organization_id, include_draft, field_types
            ),
            returnFields='_no_fields',
            size=records_count,
        )
        return _parse_cloudsearch_search_response(response)
    except Exception as e:
        logger.error(f'Error trying to search {search_criteria}: {e}')


def add_index_records(records: List[IndexRecord], resource_type: str):
    logger.info('Search - Adding records')
    mapped_records = []
    record_ids = []
    for record in records:
        mapped_records.append(
            {
                'id': record.id,
                'type': 'add',
                'fields': dataclasses.asdict(record.fields),
            }
        )
        record_ids.append(record.resource_id)
        logger.info(f'Search - Indexing: {record.id}')

    if not records:
        return

    _upload_documents_to_cloudsearch(mapped_records)

    # Do not add a record if it's already in the index.
    existing_indexes = Index.objects.filter(key__in=record_ids, type=resource_type)
    ids_to_exclude = existing_indexes.values_list('key', flat=True)
    records_to_create = [
        Index(key=record_id, type=resource_type)
        for record_id in record_ids
        if record_id not in ids_to_exclude
    ]
    Index.objects.bulk_create(records_to_create)
    existing_indexes.update(updated_at=datetime.now())


def remove_index_records(record_ids: List[Any], resource_type: str):
    mapped_records = []
    for record_id in record_ids:
        resource_id = f'{resource_type}-{record_id}'
        mapped_records.append({'id': resource_id, 'type': 'delete'})
        logger.info(f'Search - Removing index: {record_id}')
    if not mapped_records:
        return
    _upload_documents_to_cloudsearch(mapped_records)
    Index.objects.filter(key__in=record_ids, type=resource_type).delete()

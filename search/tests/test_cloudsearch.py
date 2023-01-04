from datetime import datetime, timedelta

import pytest

from search.cloudsearch import (
    _build_filter_query,
    _build_term_filter,
    _field_types_query,
    _parse_cloudsearch_search_response,
    add_index_records,
    remove_index_records,
)
from search.indexing.types import IndexRecord
from search.models import Index

resource_type = 'random_type'


@pytest.fixture
def old_record():
    record = Index.objects.create(type=resource_type, key='id')
    last_week = datetime.now() - timedelta(days=7)
    Index.objects.filter(id=record.id).update(updated_at=last_week)

    return record


@pytest.mark.functional
def test_add_index_records_should_store_indexed_record():
    add_index_records(
        [
            IndexRecord(
                'id',
                resource_type,
                'organization_id',
                'title',
                'main_content',
                'secondary_content',
                ['category'],
                False,
            ),
        ],
        resource_type=resource_type,
    )

    indexed_records = Index.objects.filter(type=resource_type, key='id')
    assert indexed_records.count() == 1


@pytest.mark.functional
def test_add_index_records_should_update_already_index_record(old_record):
    add_index_records(
        [
            IndexRecord(
                'id',
                resource_type,
                'organization_id',
                'title',
                'main_content',
                'secondary_content',
                ['category'],
                False,
            ),
        ],
        resource_type=resource_type,
    )

    indexed_records = Index.objects.get(type=resource_type, key='id')
    assert indexed_records.updated_at.date() == datetime.today().date()


@pytest.mark.functional
def test_remove_index_records(old_record):
    remove_index_records([old_record.key], resource_type)

    assert Index.objects.all().count() == 0


def test_parse_cloudsearch_search_response():
    response = {
        'hits': {
            'hit': [
                {'id': 'question-123'},
                {'id': 'policy-d9e73674-4650-4568-aa37-5341332bb0fe'},
            ]
        }
    }
    records, records_by_type = _parse_cloudsearch_search_response(response)

    assert len(records) == 2
    assert records_by_type.get('question') == ['123']
    assert records_by_type.get('policy') == ['d9e73674-4650-4568-aa37-5341332bb0fe']


def test_field_types_query_with_empty_types():
    result = _field_types_query([])

    assert result == ''


def test_field_types_query_with_field_types():
    result = _field_types_query(['question', 'policy'])

    assert result == '(or type:\'question\' type:\'policy\')'


def test_build_term_filter():
    result = _build_term_filter('key', 'some_value')

    assert result == '(term field=key \'some_value\')'


def test_build_filter_query_without_draft_documents():
    result = _build_filter_query('org_id', False, ['question'])

    assert (
        result
        == '(and (term field=organization_id \'org_id\') '
        '(term field=is_draft \'0\') '
        '(or type:\'question\'))'
    )

from datetime import datetime, timedelta

import pytest

from policy.models import Policy
from search.indexing.policy_index import policy_search_index
from search.models import Index


@pytest.mark.functional
def test_policy_search_mapper(published_policy):
    response = policy_search_index.mapper(published_policy)

    assert response.id == f'policy-{published_policy.id}'
    assert response.fields.organization_id == str(published_policy.organization_id)
    assert response.fields.category == [published_policy.category]
    assert response.fields.is_draft == 0


@pytest.mark.functional
def test_get_new_index_records(published_policy, not_published_policy):
    results = policy_search_index.get_new_index_records_queryset(
        [not_published_policy.id]
    )

    assert results.count() == 1
    assert results[0].id == published_policy.id


@pytest.mark.functional
def test_get_updated_index_records(published_policy, not_published_policy):
    last_day = datetime.today() - timedelta(days=1)
    last_week = datetime.now() - timedelta(days=7)
    Policy.objects.filter(pk=published_policy.pk).update(updated_at=last_week)
    results = policy_search_index.get_updated_index_records(last_day)

    assert results.count() == 1
    assert results[0].id == not_published_policy.id


@pytest.mark.functional
def test_get_deleted_index_records(published_policy):
    Index.objects.create(type=policy_search_index.RESOURCE_TYPE, key='random-id')
    Index.objects.create(
        type=policy_search_index.RESOURCE_TYPE, key=str(published_policy.id)
    )

    results = policy_search_index.get_deleted_index_records(Index.objects.all())

    assert results.count() == 1
    assert results[0].key == 'random-id'

import concurrent.futures as futures
import logging
import re
import timeit
import uuid
from typing import Any, List

from laika.utils.regex import SPECIAL_CHAR_FOR_GLOBAL_SEARCH
from search.cloudsearch import cloudsearch_search
from search.utils import search_model

logger = logging.getLogger('search')


def filter_match(filters, search_type):
    if not filters:
        return True

    return any([True for f in filters if f == search_type])


def _search(user, search_criteria, filters, provider):
    model = provider.get('model')
    fields = provider.get('fields')
    search_type = provider.get('type')
    qs = provider.get('qs')
    search_vector = provider.get('search_vector')
    result = []
    organization = user.organization

    if filter_match(filters, search_type):
        logger.info(f'Searching {search_type} for organization: {organization.id}')
        result = search_model(
            user,
            model,
            search_criteria,
            fields=fields,
            qs=qs,
            search_vector=search_vector,
        )
        logger.info(f'Searching {search_type} got: {len(result)} results')

    return [{'result': result, 'search_type': search_type, 'provider': provider}]


_search_models = []


def searchable_model(type, fields=[], qs=None, search_vector=None):
    def decorator(self, *args, **kwargs):
        _search_models.append(
            {
                'model': self,
                'fields': list(set(fields)),
                'type': type,
                'qs': qs,
                'search_vector': search_vector,
            }
        )
        return self

    return decorator


_launchpad_models = []


def launchpad_model(context, mapper):
    def decorator(self, *args, **kwargs):
        _launchpad_models.append({'model': self, 'context': context, 'mapper': mapper})
        return self

    return decorator


def get_launchpad_results(provider, organization_id):
    starting_time = timeit.default_timer()
    model = provider.get('model')
    context = provider.get('context')
    mapper = provider.get('mapper')
    logger.info(f'Start running context: {context}')
    response = [
        {
            "id": uuid.uuid4(),
            "context": context,
            "results": mapper(model, organization_id=organization_id),
        }
    ]
    seconds = timeit.default_timer() - starting_time
    ms = int(seconds * 1000)
    logger.info(f'Finish running context: {context} {ms} ms')
    return response


def get_launchpad_context(organization_id):
    with futures.ThreadPoolExecutor(max_workers=5) as executor:
        args = ((provider, organization_id) for provider in _launchpad_models)

        try:
            results = (
                executor.map(lambda p: get_launchpad_results(*p), args, timeout=5) or []
            )
            total_results = sum(results, [])
        except futures.TimeoutError:
            total_results = []
            logger.warning('get_launchpad_context timeout')
        return total_results


def is_valid_input(input_string):
    return re.search(SPECIAL_CHAR_FOR_GLOBAL_SEARCH, input_string)


def global_search(user, search_criteria, filters, search_models=_search_models):
    if is_valid_input(search_criteria):
        logger.info(
            'Invalid characters on global search for organization id            '
            f' {user.organization.id}: {search_criteria}'
        )
        return []

    with futures.ThreadPoolExecutor(max_workers=5) as executor:
        try:
            args = (
                (user, search_criteria, filters, provider) for provider in search_models
            )
            results = executor.map(lambda p: _search(*p), args, timeout=3) or []
            total_results = sum(results, [])
            logger.info(f'Search finished for:  {user.organization.id}')
            return total_results
        except futures._base.TimeoutError:
            logger.exception(f'Search timed out for: {user.organization.id}')
        except Exception as e:
            logger.exception(f'Error found with criteria: {search_criteria} {e}')
        return []


def _get_search_records(type: str, hits_by_type, records_qs: List[Any]):
    if not hits_by_type.get(type):
        return {type: {}}
    return {type: {str(record.id): record for record in records_qs}}


def _policy_hits(organization_id: str, hits_by_type):
    from policy.models import Policy
    from search.indexing.policy_index import policy_search_index

    policy_hits = hits_by_type.get(policy_search_index.RESOURCE_TYPE)
    policy_qs = (
        Policy.objects.filter(organization_id=organization_id, id__in=policy_hits)
        if policy_hits
        else []
    )
    return _get_search_records(
        policy_search_index.RESOURCE_TYPE, hits_by_type, policy_qs
    )


def _question_hits(organization_id: str, hits_by_type):
    from library.models import Question
    from search.indexing.question_index import question_search_index

    resource_type = question_search_index.RESOURCE_TYPE
    question_hits = hits_by_type.get(resource_type)
    default_questions_qs = (
        Question.objects.filter(
            library_entry__organization_id=organization_id,
            id__in=question_hits,
            default=True,
        )
        if question_hits
        else []
    )
    default_from_equivalents_qs = (
        Question.objects.prefetch_related('equivalent_questions').filter(
            library_entry__organization_id=organization_id,
            equivalent_questions__id__in=question_hits,
            default=True,
        )
        if question_hits
        else []
    )
    result = _get_search_records(resource_type, hits_by_type, default_questions_qs)

    for question in default_from_equivalents_qs:
        equivalent_question_ids = question.equivalent_questions.values_list(
            'id', flat=True
        )
        for equivalent_id in equivalent_question_ids:
            result[resource_type][str(equivalent_id)] = question

    return result


def search(
    search_criteria: str,
    organization_id: str,
    field_types: List[str],
    records_count=10,
    include_draft=False,
):
    hits, hits_by_type = cloudsearch_search(
        search_criteria,
        organization_id,
        field_types or [],
        records_count,
        include_draft,
    )
    records = {
        **_policy_hits(organization_id, hits_by_type),
        **_question_hits(organization_id, hits_by_type),
    }
    results = [
        {
            'id': hit_id,
            'type': hit_type,
            'response': records.get(hit_type, {}).get(hit_id),
        }
        for hit_type, hit_id in hits
        if records.get(hit_type, {}).get(hit_id)
    ]
    return results

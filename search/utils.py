import itertools
import re
import uuid
from operator import itemgetter
from string import Template

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from psycopg2.extensions import adapt

from laika.settings import SEARCH_THRESHOLD
from laika.utils.regex import NO_WORD
from search import search

TRUNCATE_VALUE = 150


def get_content_text(text, match):
    match_end_index = match.end()
    match_start_index = match.start()
    text_length = len(text)

    if text_length <= TRUNCATE_VALUE:
        return text

    if match_end_index < TRUNCATE_VALUE:
        return text[0:TRUNCATE_VALUE]

    if match_end_index > TRUNCATE_VALUE:
        last_text_length = text_length - match_end_index
        last_index = (
            match_end_index + last_text_length - 1
            if last_text_length <= 125
            else match_end_index + 125
        )
        start_index = (
            match_start_index - 50
            if match_start_index > TRUNCATE_VALUE
            else match_start_index - 25
        )

        return text[start_index:last_index]


def get_result_content(description, content, query):
    match_rule = '|'.join(re.sub(NO_WORD, ' ', query).strip().split(' '))
    description_match = re.search(match_rule, description, flags=re.IGNORECASE)
    if description_match:
        return get_content_text(description, description_match)

    if content is None:
        content = ''
    content_match = re.search(match_rule, content)
    if content_match:
        return get_content_text(content, content_match)

    return ''


def get_search_result_values(custom_fields, result, search_type, query):
    tags = getattr(result, 'tags', None)
    _id = getattr(result, 'id', '')
    logo_file = getattr(result, 'logo', None)
    description = getattr(result, 'description', '')
    content = (
        getattr(result, 'evidence_text', '')
        if search_type == 'document'
        else getattr(result, 'policy_text', '')
    )

    if search_type == 'vendor':
        _id = result.organizationvendor_set.first().id

    if search_type == 'document':
        _id = result.evidence.id

    program_id = getattr(result, 'program_id', None)

    fields_dic = {field: getattr(result, field, None) for field in custom_fields}

    return {
        'id': _id,
        'name': getattr(result, 'name', ''),
        'description': get_result_content(description, content, query),
        'meta': {
            # This is for apollo issue not differencing between programs
            'id': program_id,
            'program_id': program_id,
        },
        'tags': tags.all() if tags else [],
        'logo': logo_file.url if logo_file else None,
        'custom_fields': fields_dic,
    }


def format_search_result(custom_fields, search_result, search_type, query):
    return [
        {
            **get_search_result_values(custom_fields, result, search_type, query),
            'search_type': search_type,
        }
        for result in search_result
    ]


class PartialSearchQuery(SearchQuery):
    '''
    Alter the tsquery executed by SearchQuery to accept partial search
    '''

    def as_sql(self, compiler, connection):
        expression = self.source_expressions[0]
        expression_value = expression.__getstate__()['value']
        template = Template('$value:*')
        value = adapt(template.substitute(value=' & '.join(expression_value.split())))

        if self.config:
            config_sql, config_params = compiler.compile(self.config)
            template = 'to_tsquery({}::regconfig, {})'.format(config_sql, value)
            params = config_params

        else:
            template = 'to_tsquery({})'.format(value)
            params = []

        if self.invert:
            template = '!!({})'.format(template)

        return template, params


DEFAULT_SEARCH_FIELDS = ['name', 'description', 'tags']
WEIGHTS = ['A', 'B', 'C', 'D']
WEIGHTS_VALUES = [0.2, 0.4, 0.8, 1.0]


def search_query(organization, model, qs, rank, filter_by_org=True):
    filter = {'rank__gte': SEARCH_THRESHOLD}

    if filter_by_org and hasattr(model, 'organization'):
        filter['organization'] = organization

    return qs.annotate(rank=rank).filter(**filter).distinct().order_by('-rank')


def filter_search_duplicates(results):
    ids = []
    unique_result = []
    # This is because the django search can return duplicated records,
    # but with a little change on the rank field amount.
    for r in results:
        if r.id not in ids:
            unique_result.append(r)
            ids.append(r.id)

    return unique_result


def get_query_set(user, model, qs):
    return qs(user, model) if qs else model.objects


def search_model(
    user,
    model,
    search_criteria,
    fields,
    qs,
    # This is for handling cases where the search is on related models
    search_vector,
):
    organization = user.organization
    search_fields = DEFAULT_SEARCH_FIELDS + (fields or [])
    vector = search_vector
    weight_index = 0

    if not vector:
        for field in search_fields:
            if hasattr(model, field):
                field_name = field if field != 'tags' else 'tags__name'
                v = SearchVector(field_name, weight=WEIGHTS[weight_index])
                vector = v if vector is None else vector + v
                weight_index += 1

    query = PartialSearchQuery(search_criteria)
    rank = SearchRank(vector, query, weights=WEIGHTS_VALUES)
    query_set = get_query_set(user, model, qs)
    filter_by_org = qs is None
    results = search_query(organization, model, query_set, rank, filter_by_org)

    return filter_search_duplicates(results)


def parsed_global_search(filters, search_criteria, user):
    results = search.global_search(user, search_criteria, filters)
    formatted_results = []

    for r in results:
        provider = r.get('provider')
        fields = provider['fields'] if provider and 'fields' in provider else []

        formatted = format_search_result(
            fields, r.get('result', []), r.get('search_type'), search_criteria
        )
        formatted_results = formatted_results + formatted

    return formatted_results


def to_cmd_k_results(results):
    results_by_type = itertools.groupby(results, key=itemgetter('search_type'))

    return [
        {"id": uuid.uuid4(), "context": _type, "results": list(results)}
        for _type, results in results_by_type
    ]


def batch_iterator(qs, chunk_size):
    items = []
    for item in qs.iterator(chunk_size=chunk_size):
        if len(items) == chunk_size:
            yield items, False
            items = []
        items.append(item)
    if len(items) > 0:
        yield items, True

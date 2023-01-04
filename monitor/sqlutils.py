from typing import Optional, Sequence

import sqlparse
from sqlparse import parse
from sqlparse.sql import Identifier, IdentifierList, Token, Where
from sqlparse.tokens import Keyword

Wildcard = sqlparse.tokens.Token.Wildcard
Integer = sqlparse.tokens.Token.Literal.Number
Whitespace = sqlparse.tokens.Token.Text.Whitespace


def _get_table_names(query: str) -> list[str]:
    selected_tables = get_selected_tables(query)
    return [table_name for _, table_name, _ in selected_tables]


def is_cloud_table(table: str) -> bool:
    return bool(extract_vendor(table))


def extract_vendor(table_name) -> str:
    prefix = table_name.split('_')[0].lower()
    if prefix == 'azuread':
        prefix = 'azure'
    if prefix not in STEAMPIPE_SERVICES:
        return ''
    return prefix


def _token_is_table_name(token: Token) -> bool:
    return isinstance(token, Identifier)


def stringify_token_list(tokens: list[sqlparse.sql.Token]) -> str:
    return ''.join([token.value for token in tokens])


def delete_where_clause(query: str) -> str:
    tokens = get_tokens(query)
    where_clause_index = None
    for index, token in enumerate(tokens):
        if isinstance(token, Where):
            where_clause_index = index
    if where_clause_index is not None:
        del tokens[where_clause_index]
    return stringify_token_list(tokens)


def where_clause(query: str) -> str:
    tokens = get_tokens(query)
    for index, token in enumerate(tokens):
        if isinstance(token, Where):
            return str(tokens[index])
    return ''


LIMIT = 'LIMIT'
ALL = 'ALL'


def delete_limit_clause(query: str) -> str:
    tokens = get_tokens(query)
    limit_clause_index = None
    for index, token in enumerate(tokens):
        if _token_is_keyword(token, LIMIT):
            limit_clause_index = index
    if limit_clause_index:
        for index in reversed(range(limit_clause_index, len(tokens))):
            del tokens[index]
    return stringify_token_list(tokens)


def add_limit_clause(query: str, limit: int) -> str:
    limit_removed_query = delete_limit_clause(query)
    return f'{limit_removed_query.strip()} limit {limit}'


def get_selected_tables(
    query: str, verify_table=_token_is_table_name
) -> Sequence[tuple[int, str, Optional[str]]]:
    tokens = get_tokens(query)
    collecting = False
    selected_tables = []
    for index, token in enumerate(tokens):
        if collecting and verify_table(token):
            selected_tables.append((index, token.get_real_name(), token.get_alias()))
        collecting = _token_is_collecting(token, collecting)
    return selected_tables


def _token_is_collecting(token: Token, collecting: bool) -> bool:
    if collecting:
        return _token_is_keyword(token, JOIN) or token.ttype is not Keyword
    return _token_is_keyword(token, FROM) or _token_is_keyword(token, JOIN)


def _token_is_keyword(token: Token, keyword: str) -> bool:
    return token.ttype is Keyword and keyword in token.value.upper()


def get_tokens(query: str) -> list[Token]:
    parsed_query = parse(query)[0]
    token_values = []
    for token in parsed_query:
        if isinstance(token, IdentifierList):
            for nested_token in token.tokens:
                token_values.append(nested_token)
        else:
            token_values.append(token)
    return token_values


def _token_is_identifier(token):
    return (
        token.ttype is Wildcard
        or isinstance(token, IdentifierList)
        or isinstance(token, Identifier)
    )


def get_raw_selected_columns(query: str) -> str:
    parsed_query = parse(query)[0]
    tokens = []
    for token in parsed_query:
        if _token_is_keyword(token, FROM):
            break
        if str(token.value).lower() == 'select':
            continue
        tokens.append(token)
    return stringify_token_list(tokens).strip()


def _is_collecting_columns(token: Token, collecting: bool) -> bool:
    return collecting and _token_is_identifier(token)


def replace_selected_columns(query: str, new_selection: str) -> str:
    parsed_query = parse(query)[0]
    collecting = True
    token_values = []
    place_holder = '__replace_select__'
    for token in parsed_query:
        token_value = token.value
        if _is_collecting_columns(token, collecting):
            collecting = False
            token_value = place_holder
        token_values.append(token_value)
    return ''.join(token_values).replace(place_holder, new_selection)


def compatible_queries(a: str, b: str) -> bool:
    query_a = replace_selected_columns(a, '*').replace(';', '') if a else ''
    query_b = replace_selected_columns(b, '*').replace(';', '') if b else ''
    return query_a == query_b


def add_criteria(query: str, criteria: str) -> str:
    if not criteria:
        return query
    where = where_clause(query).rstrip()
    if where:
        return query.replace(where, f'{where} AND {criteria}')
    else:
        return add_where(query.rstrip('\n ;'), f'WHERE {criteria}')


def not_in(exclude_field: str, values: list[str]) -> str:
    if not values:
        return ''
    str_values = ', '.join(repr(value) for value in values)
    return f'{exclude_field} NOT IN ({str_values})'


def add_where(query: str, where: str) -> str:
    after_kws = ('GROUP BY', 'HAVING', 'ORDER BY', 'LIMIT', 'OFFSET')
    base_query = query.upper()
    for kw in after_kws:
        index = base_query.rfind(kw)
        if index >= 0:
            after = query[index:]
            return query.replace(after, f'{where} {after}')
    return f'{query} {where}'


FROM = 'FROM'
JOIN = 'JOIN'

STEAMPIPE_SERVICES = ['aws', 'heroku', 'gcp', 'azure', 'okta', 'digitalocean']

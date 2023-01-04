from django.db import DatabaseError

from monitor.laikaql import (
    action_item,
    audit,
    control,
    document,
    evidence_request,
    monitor,
    monitor_result,
    officer,
    people,
    policy,
    subtask,
    task,
    team,
    team_member,
    training,
    training_alumni,
    vendor,
)
from monitor.laikaql.lo import SQL_TO_LO_MAPPING, build_laika_object_query
from monitor.sqlutils import get_selected_tables, get_tokens
from monitor.type_hints import QueryBuilder
from organization.models import Organization


def build_raw_query(organization: Organization, query: str) -> str:
    selected_tables = get_selected_tables(query)
    tokens = get_tokens(query)
    for index, table_name, alias in selected_tables:
        query_builder = get_query_builder_by_alias(table_name)
        raw_spec_query = query_builder(organization)
        tokens[index].value = f'({raw_spec_query}) AS {alias or table_name}'
    token_values = [token.value for token in tokens]
    return ''.join(token_values)


def get_query_builder_by_alias(alias: str) -> QueryBuilder:
    if alias in ALIASES:
        return ALIASES[alias]
    raise DatabaseError(f'table "{alias}" does not exist')


APP_ALIASES: dict[str, QueryBuilder] = {
    'policies': policy.build_query,
    'people': people.build_query,
    'monitors': monitor.build_query,
    'documents': document.build_query,
    'monitor_results': monitor_result.build_query,
    'controls': control.build_query,
    'evidence_requests': evidence_request.build_query,
    'vendors': vendor.build_query,
    'audits': audit.build_query,
    'teams': team.build_query,
    'officers': officer.build_query,
    'team_members': team_member.build_query,
    'training_alumni': training_alumni.build_query,
    'trainings': training.build_query,
    'action_items': action_item.build_query,
    'tasks': task.build_query,
    'subtasks': subtask.build_query,
}


ALIASES: dict[str, QueryBuilder] = {
    **{
        table: build_laika_object_query(lo_type)
        for table, lo_type in SQL_TO_LO_MAPPING.items()
    },
    **APP_ALIASES,
}

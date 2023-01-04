import re
from typing import Any, Iterator

from monitor.models import OrganizationMonitor
from monitor.result import Result
from monitor.sqlutils import get_raw_selected_columns, get_selected_tables

TEMPLATE_PREFIX = 'tv'


def placeholders_from_template(template: str) -> list[str]:
    return re.findall(r'(\$[\w\d]+\.[\w\d]+)', template)


def get_template_key_from_column(column: str) -> str:
    return column.replace(f'{TEMPLATE_PREFIX}_', '').replace('__', '.')


def build_column_from_template_key(key: str) -> str:
    return f'{TEMPLATE_PREFIX}_{key.replace(".", "__")}'


def get_template_columns_and_data(
    columns: list[str], data: list[list]
) -> tuple[list[str], list[list]]:
    template_columns = [
        column for column in columns if column.startswith(TEMPLATE_PREFIX)
    ]
    template_data = (
        [row[-len(template_columns) :] for row in data] if template_columns else []
    )
    return template_columns, template_data


def get_original_columns_and_data(
    columns: list[str], data: list[list], template_columns_length: int
) -> tuple[list[str], list[list]]:
    if not template_columns_length:
        return columns, data
    original_columns = columns[:-template_columns_length]
    original_data = [keep_columns(row, original_columns) for row in data]
    return original_columns, original_data


def keep_columns(row: list, original_columns: list[str]) -> list:
    return row[: len(original_columns)]


def build_template_argument(template_columns: list[str], row: list) -> dict[str, str]:
    return {
        get_template_key_from_column(key): value
        for key, value in zip(template_columns, row)
    }


def build_template_arguments_from_template_results(
    template_columns: list[str], template_data: list[list]
) -> list[dict[str, str]]:
    return [build_template_argument(template_columns, row) for row in template_data]


def build_fix_links(organization_monitor: OrganizationMonitor, result: dict[str, Any]):
    try:
        fix_me_link = organization_monitor.monitor.fix_me_link
        if not fix_me_link or not result or organization_monitor.monitor.is_custom():
            return []
        if not placeholders_from_template(fix_me_link):
            return [fix_me_link] * len(result['data'])
        variables = result.get('variables', {})
        return build_fix_me_links(fix_me_link, variables)
    except (ValueError, KeyError):
        return []


def build_fix_me_links(fix_me_link, variables):
    links = []
    link_variables = placeholders_from_template(fix_me_link)
    for variable in variables:
        link = fix_me_link
        for link_variable in link_variables:
            key = link_variable.replace('$', '').lower()
            link = link.replace(link_variable, str(variable[key]))
        links.append(link)
    return links


def build_columns_for_variables(
    table_identifiers: dict[str, str], variables: list[str]
) -> Iterator[str]:
    for variable in variables:
        table, column = table_column(variable)
        if table in table_identifiers:
            yield (
                f'{table_identifiers[table]}.{column} '
                f'as {TEMPLATE_PREFIX}_{table}__{column}'
            )


def table_column(placeholder: str) -> list[str]:
    return placeholder.lower().strip('$').split('.')[:2]


def get_selected_tables_identifiers(query: str) -> dict[str, str]:
    return {
        real_name: alias if alias else real_name
        for _, real_name, alias in get_selected_tables(query)
    }


def build_query_for_variables(
    original_query: str, template: str, exclusion_field: str
) -> str:
    variables = []
    if template:
        variables = placeholders_from_template(template)
    if exclusion_field:
        variables.append(exclusion_field)
    if not variables:
        return original_query
    tables_identifiers = get_selected_tables_identifiers(original_query)
    raw_columns_for_variables = ', '.join(
        build_columns_for_variables(tables_identifiers, variables)
    )
    if not raw_columns_for_variables:
        return original_query
    raw_selected_columns = get_raw_selected_columns(original_query)
    new_selected_columns = f'{raw_selected_columns}, {raw_columns_for_variables}'
    return original_query.replace(raw_selected_columns, new_selected_columns, 1)


def extract_placeholders(result: Result) -> Result:
    template_columns, template_data = get_template_columns_and_data(
        result.columns, result.data
    )
    if result.error or not template_columns:
        return result
    original_columns, original_data = get_original_columns_and_data(
        result.columns, result.data, len(template_columns)
    )
    variables = build_template_arguments_from_template_results(
        template_columns, template_data
    )

    return Result(data=original_data, columns=original_columns, variables=variables)

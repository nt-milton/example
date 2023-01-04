import re
from collections import defaultdict
from difflib import get_close_matches
from itertools import chain
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

from monitor import template
from monitor.laikaql.builder import ALIASES
from monitor.laikaql.lo import SQL_TO_LO_MAPPING, get_columns
from monitor.sqlutils import STEAMPIPE_SERVICES, _get_table_names, extract_vendor
from monitor.steampipe import run_query
from organization.models import Organization
from program.models import SubTask

from .models import MonitorRunnerType, MonitorType
from .runner import dry_run

STEAMPIPE_QUERY = """
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = '{}';
    """


ALLOWED_INTERNAL_ROUTES = [
    'policies',
    'monitors',
    'documents',
    'organization',
    'datarooms',
    'reports',
    'audits',
    'training',
    'controls',
    'people',
    'lob',
]


def mock_organization() -> Organization:
    return Organization(id=uuid4())


def validate_fix_me_link(fix_me_link: str, source_query: str = None) -> None:
    if fix_me_link:
        variables = template.placeholders_from_template(fix_me_link)
        tables = get_tables_and_columns(variables)
        is_external_link = fix_me_link.startswith('http')
        if is_external_link:
            verify_valid_link(fix_me_link)
        else:
            verify_internal_link(fix_me_link)
        verify_columns(tables)
        if source_query:
            validate_placeholder_with_query(
                set(tables.keys()), _get_table_names(source_query)
            )


def validate_placeholder_with_query(
    placeholder_tables: set[str], query_tables: list[str]
):
    if not placeholder_tables.issubset(query_tables):
        raise ValidationError('Placeholder tables do not match query')


def verify_columns_in_allowed_columns(
    columns: list, allowed_columns: list, table_name: str
) -> None:
    for column in columns:
        if column not in allowed_columns:
            raise ValidationError(f'{column} is not a valid column in {table_name}')


def get_tables_and_columns(variables: list[str]) -> dict:
    tables = defaultdict(list)
    for variable in variables:
        splited_variable = variable.split('.')
        if len(splited_variable) < 2:
            raise ValidationError(
                'The structure of the variable should be "$table.column"'
            )
        table, column = template.table_column(variable)
        tables[table].append(column)
    return tables


def get_vendor_from_table_name(table_name: str) -> str:
    vendor_name = extract_vendor(table_name)
    try:
        index = STEAMPIPE_SERVICES.index(vendor_name)
        return STEAMPIPE_SERVICES[index]
    except ValueError:
        return ''


def get_allowed_columns(table_name: str) -> list[str]:
    vendor_name = get_vendor_from_table_name(table_name)
    if vendor_name:
        query_result = run_query(STEAMPIPE_QUERY.format(table_name))
        allowed_columns = list(chain.from_iterable(query_result.data))
    elif table_name in SQL_TO_LO_MAPPING:
        spec = SQL_TO_LO_MAPPING[table_name]
        allowed_columns = get_columns(spec)
    elif table_name in ALIASES:
        allowed_columns = dry_run(
            mock_organization(),
            f'select * from {table_name} limit 0',
            '',
            MonitorRunnerType.LAIKA_CONTEXT,
        ).columns
    else:
        raise ValidationError(f'{table_name} is not a valid table')
    return allowed_columns


def verify_single_table(table: str, columns: list[str]) -> None:
    allowed_columns = get_allowed_columns(table)
    verify_columns_in_allowed_columns(columns, allowed_columns, table)


def verify_columns(tables: dict) -> None:
    for table, columns in tables.items():
        verify_single_table(table, columns)


def verify_valid_link(fix_me_link: str):
    """Validate website into valid URL"""
    validate = URLValidator()
    try:
        validate(re.sub(r'[\$_]', '', str(fix_me_link)))
    except ValidationError:
        raise ValidationError(f'{fix_me_link} is not a valid link')


def verify_internal_link(fix_me_link: str):
    if not fix_me_link.startswith('/'):
        raise ValidationError('Internal link must start with "/"')
    link_components = re.findall(r'\w+', fix_me_link) or []
    internal_link = link_components[0] if len(link_components) > 0 else ''
    if internal_link not in ALLOWED_INTERNAL_ROUTES:
        suggested_word = get_close_matches(internal_link, ALLOWED_INTERNAL_ROUTES)
        if not suggested_word:
            raise ValidationError(f'{internal_link} is not a valid internal link')
        else:
            raise ValidationError(
                f'{internal_link} is not a valid link. '
                f'Did you mean {suggested_word[0]}?'
            )


def validate_exclude_field(exclude_field, source_query=None):
    if exclude_field:
        splitted_exclude_field = exclude_field.split('.')
        if len(splitted_exclude_field) != 2:
            raise ValidationError('Invalid exclude field')
        table, column = exclude_field.split('.')
        verify_single_table(table, [column])
        if source_query:
            validate_placeholder_with_query({table}, _get_table_names(source_query))


def validate_subtask_reference(subtask_reference: str, monitor_type: str):
    if subtask_reference:
        if monitor_type == MonitorType.CUSTOM:
            raise ValidationError('Only a system monitor can reference subtasks.')

        subtask_uuids = list(set(subtask_reference.replace(' ', '').split()))
        references = [
            SubTask.objects.filter(reference_id=subtask_uuid).exists()
            for subtask_uuid in subtask_uuids
        ]
        if not all(references):
            raise ValidationError('All referenced ids must exist.')

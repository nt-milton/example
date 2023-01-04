from typing import List

from monitor.type_hints import QueryBuilder
from objects.models import LaikaObjectType
from objects.system_types import (
    ACCOUNT,
    CHANGE_REQUEST,
    DEVICE,
    EVENT,
    JSON,
    MONITOR,
    PULL_REQUEST,
    REPOSITORY,
    SERVICE_ACCOUNT,
    USER,
    ObjectTypeSpec,
)
from organization.models import Organization

FALSE_CRITERIA = ' 1 = 0 '


def build_laika_object_query(spec: ObjectTypeSpec) -> QueryBuilder:
    def build_raw_query_for_spec(organization: Organization) -> str:
        columns = ['id as lo_id'] + build_columns_for_spec(spec)
        table = 'objects_laikaobject'
        laika_object_type = LaikaObjectType.objects.filter(
            type_name=spec.type, organization=organization
        ).first()
        if laika_object_type:
            conditions = f'object_type_id={laika_object_type.id} AND deleted_at is null'
        else:
            conditions = FALSE_CRITERIA
        return build_raw_select_query(columns, table, conditions)

    return build_raw_query_for_spec


def convert_name_to_column(name):
    return name.replace(' ', '_').lower()


def get_columns(spec: ObjectTypeSpec):
    for attribute in spec.attributes:
        yield convert_name_to_column(attribute['name'])


def build_columns_for_spec(spec: ObjectTypeSpec) -> List[str]:
    columns = []
    for attribute in spec.attributes:
        name = attribute['name']
        key = convert_name_to_column(name)
        operator = '->>' if attribute['attribute_type'] != JSON else '->'
        columns.append(f"data{operator}'{name}' \"{key}\"")
    return columns


def build_raw_select_query(
    columns: List[str], table: str, conditions: str = None
) -> str:
    return (
        f'SELECT {", ".join(columns)} FROM {table}'
        f'{f" WHERE {conditions}" if conditions else ""}'
    )


SQL_TO_LO_MAPPING = {
    'lo_users': USER,
    'lo_change_requests': CHANGE_REQUEST,
    'lo_pull_requests': PULL_REQUEST,
    'lo_monitors': MONITOR,
    'lo_events': EVENT,
    'lo_accounts': ACCOUNT,
    'lo_repositories': REPOSITORY,
    'lo_devices': DEVICE,
    'lo_service_accounts': SERVICE_ACCOUNT,
}
LO_TO_SQL_MAPPING = {
    lo_type.type: table for table, lo_type in SQL_TO_LO_MAPPING.items()
}

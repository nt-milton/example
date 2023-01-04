import logging

from django.db import transaction

from objects.models import LaikaObjectType
from seeder.seeders.commons import (
    are_columns_empty,
    are_columns_required_empty,
    get_headers,
)

logger = logging.getLogger('seeder')

TYPE_FIELDS_REQUIRED = [
    'display_name',
    'type_name',
    'sort_index',
    'icon_name',
    'color',
    'description',
]

TYPE_FIELDS = [*TYPE_FIELDS_REQUIRED, 'is_system_type']


def seed(organization, workbook):
    status_detail = []
    if 'object_types' not in workbook.sheetnames:
        return status_detail

    object_types_sheet = workbook['object_types']

    if object_types_sheet.cell(row=2, column=1).value is None:
        return status_detail

    headers = get_headers(object_types_sheet)

    for row in object_types_sheet.iter_rows(min_row=2):
        dictionary = dict(zip(headers, [c.value for c in row[0 : len(headers)]]))
        if are_columns_empty(dictionary, TYPE_FIELDS):
            continue
        try:
            with transaction.atomic():
                if are_columns_required_empty(dictionary, TYPE_FIELDS_REQUIRED):
                    status_detail.append(
                        'Error seeding object type with name: '
                        f'{dictionary["display_name"]}, '
                        f'Fields: {TYPE_FIELDS_REQUIRED} required.'
                    )
                    continue
                LaikaObjectType.objects.update_or_create(
                    organization=organization,
                    type_name=dictionary['type_name'].strip(),
                    defaults={
                        'display_name': dictionary['display_name'],
                        'is_system_type': bool(dictionary['is_system_type']),
                        'display_index': dictionary['sort_index'],
                        'color': dictionary['color'],
                        'icon_name': dictionary['icon_name'],
                        'description': dictionary['description'],
                    },
                )

        except Exception as e:
            logger.warning(
                f'Object type with name: {dictionary["display_name"]} has failed. {e}'
            )
            status_detail.append(
                'Error seeding object type with name: '
                f'{dictionary["display_name"]}. Error: {e}'
            )
    return status_detail

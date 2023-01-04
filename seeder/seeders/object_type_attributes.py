import logging

from django.db import transaction

from objects.metadata import Metadata
from objects.models import Attribute, LaikaObjectType
from objects.types import AttributeTypeFactory, Types
from seeder.seeders.commons import (
    are_columns_empty,
    are_columns_required_empty,
    get_headers,
)

logger = logging.getLogger('seeder')

ATTRIBUTE_FIELDS_REQUIRED = [
    'object_type_type_name',
    'name',
    'sort_index',
    'attribute_type',
]

ATTRIBUTE_FIELDS = [
    *ATTRIBUTE_FIELDS_REQUIRED,
    'min_width',
    'default_value',
    'select_options',
    'is_protected',
]


def seed(organization, workbook):
    status_detail = []
    if 'object_type_attributes' not in workbook.sheetnames:
        return status_detail

    attributes_sheet = workbook['object_type_attributes']

    if attributes_sheet.cell(row=2, column=1).value is None:
        return status_detail

    headers = get_headers(attributes_sheet)

    for row in attributes_sheet.iter_rows(min_row=2):
        dictionary = dict(zip(headers, [c.value for c in row[0 : len(headers)]]))
        if are_columns_empty(dictionary, ATTRIBUTE_FIELDS):
            continue
        try:
            with transaction.atomic():
                if are_columns_required_empty(dictionary, ATTRIBUTE_FIELDS_REQUIRED):
                    status_detail.append(
                        'Error seeding type attribute with name: '
                        f'{dictionary["name"]},'
                        f'Fields: {ATTRIBUTE_FIELDS_REQUIRED} required.'
                    )
                    continue
                object_type = None
                if dictionary['object_type_type_name']:
                    object_type = LaikaObjectType.objects.get(
                        organization=organization,
                        type_name=dictionary['object_type_type_name'],
                    )
                if object_type is None:
                    raise ValueError(
                        'Object Type with name: '
                        f'{dictionary["object_type_type_name"]}'
                        ' not found.'
                    )

                if dictionary['attribute_type'] not in Types.__members__:
                    raise ValueError(
                        f'Invalid attribute type: {dictionary["attribute_type"]}.'
                    )
                Attribute.objects.update_or_create(
                    object_type=object_type,
                    name=dictionary['name'].strip(),
                    defaults={
                        'sort_index': dictionary['sort_index'],
                        'attribute_type': dictionary['attribute_type'],
                        'min_width': dictionary['min_width'],
                        'is_required': dictionary['is_required']
                        if 'is_required' in dictionary
                        else False,
                        '_metadata': get_metadata(dictionary).to_json(),
                    },
                )

        except Exception as e:
            logger.warning(
                f'Type attribute with name: {dictionary["name"]} has failed. {e}'
            )
            status_detail.append(
                'Error seeding type attribute with name: '
                f'{dictionary["name"]}. Error: {e}'
            )
    return status_detail


def get_metadata(dictionary):
    default_value = None
    if dictionary['default_value'] is not None:
        attribute = Attribute()
        attribute.attribute_type = dictionary['attribute_type']
        attribute.name = dictionary['name'].strip()
        attribute_type = AttributeTypeFactory.get_attribute_type(attribute)
        default_value = attribute_type.format(dictionary['default_value'])
    metadata = Metadata()
    metadata.is_protected = bool(dictionary.get('is_protected'))
    metadata.default_value = default_value
    metadata.set_select_options_from_csv(dictionary.get('select_options'))
    return metadata

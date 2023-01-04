import copy
from unittest.mock import patch

import pytest

from objects.migrate import (
    AttributeRename,
    _bulk_add,
    _bulk_rename,
    migrate_lo,
    update_attributes_order,
    update_non_default_fields_in_spec_attributes,
)
from objects.models import Attribute, LaikaObject
from objects.system_types import TEXT, USER, ObjectTypeSpec, resolve_laika_object_type
from organization.tests import create_organization

ATT_TITLE = 'Title'
TEST_EMAIL = 'test@heylaika.com'
USERS = [dict(id=1, email=TEST_EMAIL, title='test')]


@pytest.fixture()
def lo_type():
    organization = create_organization()
    lo_type = resolve_laika_object_type(organization, USER)
    for data in USERS:
        LaikaObject.objects.update_or_create(
            data__id=data['id'], object_type=lo_type, defaults={'data': data}
        )
    return lo_type


@pytest.mark.functional
def test_lo_add_column_populate_existing_tables(lo_type):
    new_column_name = 'new'

    def simulate_new_column_user_spec():
        spec = copy.deepcopy(USER)
        spec.attributes.append(
            {
                'name': new_column_name,
                'attribute_type': TEXT,
                'sort_index': 10,
                '_metadata': {'is_protected': True},
            }
        )
        return spec

    with patch('objects.migrate.connection') as cnn:
        mock_cursor = cnn.cursor.return_value.__enter__.return_value
        migrate_lo(simulate_new_column_user_spec(), new=[new_column_name])

        mock_cursor.execute.assert_called_once_with(
            _bulk_add(new_column_name), [lo_type.id]
        )
    assert Attribute.objects.filter(name=new_column_name).exists()


@pytest.mark.functional
def test_lo_rename_column_populate_existing_tables(lo_type):
    attribute_rename = AttributeRename(old=ATT_TITLE, new='titlev2')
    with patch('objects.migrate.connection') as cnn:
        mock_cursor = cnn.cursor.return_value.__enter__.return_value

        migrate_lo(USER, rename=[attribute_rename])

        mock_cursor.execute.assert_called_once_with(
            _bulk_rename(attribute_rename), [lo_type.id]
        )
    assert Attribute.objects.filter(name=attribute_rename.new).exists()


def generate_raw_attribute(name, index):
    return {
        'name': name,
        'attribute_type': 'TEXT',
        '_metadata': {'is_protected': True},
        'sort_index': index,
    }


@pytest.mark.functional
def test_update_non_default_fields_in_spec_attributes():
    attribute_1 = 'Attribute 1'
    attribute_2 = 'Attribute 2'
    spec = ObjectTypeSpec(
        display_name='Spec',
        type='spec',
        icon='',
        color='',
        attributes=[
            generate_raw_attribute(attribute_1, 0),
            generate_raw_attribute(attribute_2, 1),
        ],
    )
    organization = create_organization()
    resolve_laika_object_type(organization, spec)
    expected_min_width = 0
    expected_is_manually_editable = False
    for attribute in spec.attributes:
        attribute.update(
            {
                'min_width': expected_min_width,
                'is_manually_editable': expected_is_manually_editable,
            }
        )
    update_non_default_fields_in_spec_attributes(spec)
    for attribute in [attribute_1, attribute_2]:
        attribute_instance = Attribute.objects.get(
            object_type__type_name=spec.type, name=attribute
        )
        assert attribute_instance.min_width == expected_min_width
        assert attribute_instance.is_manually_editable == expected_is_manually_editable


@pytest.mark.functional
def test_order_attributes():
    attribute_1 = 'Attribute 1'
    attribute_2 = 'Attribute 2'
    spec = ObjectTypeSpec(
        display_name='Spec',
        type='spec',
        icon='',
        color='',
        attributes=[
            generate_raw_attribute(attribute_1, 0),
            generate_raw_attribute(attribute_2, 1),
        ],
    )
    organization = create_organization()
    resolve_laika_object_type(organization, spec)
    spec.attributes = [
        generate_raw_attribute(attribute_2, 0),
        generate_raw_attribute(attribute_1, 1),
    ]
    update_attributes_order(spec)
    assert (
        Attribute.objects.get(
            object_type__type_name=spec.type, name=attribute_1
        ).sort_index
        == 1
    )
    assert (
        Attribute.objects.get(
            object_type__type_name=spec.type, name=attribute_2
        ).sort_index
        == 0
    )


@pytest.mark.functional
def test_lo_delete_column(lo_type):
    def simulate_delete_user_spec():
        spec = copy.deepcopy(USER)
        attribute, *_ = [att for att in spec.attributes if att['name'] == ATT_TITLE]
        spec.attributes.remove(attribute)
        return spec

    migrate_lo(simulate_delete_user_spec(), delete=[ATT_TITLE])

    lo = LaikaObject.objects.filter(data__email=TEST_EMAIL).first()
    assert ATT_TITLE not in lo.data

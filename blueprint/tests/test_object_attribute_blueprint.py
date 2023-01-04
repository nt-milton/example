from typing import Tuple
from unittest.mock import patch

import pytest
from django.contrib.admin import AdminSite

from blueprint.admin import ObjectAttributeBlueprintAdmin
from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.commons import AirtableSync
from blueprint.constants import (
    ATTRIBUTE_TYPE,
    DEFAULT_VALUE,
    DISPLAY_INDEX,
    IS_PROTECTED,
    LAST_MODIFIED,
    MIN_WIDTH,
    NAME,
    OBJECT_ATTRIBUTE_REQUIRED_FIELDS,
    REFERENCE_ID,
    SELECT_OPTIONS,
    TYPE_NAME,
)
from blueprint.models.object_attribute import ObjectAttributeBlueprint
from blueprint.tests.test_commons import (
    DATETIME_MOCK,
    RECORD_ID_MOCK,
    get_airtable_sync_class,
)
from user.models import User

TEXT = 'TEXT'


def create_object_attribute(reference_id, name, display_index):
    return ObjectAttributeBlueprint.objects.get_or_create(
        reference_id=reference_id,
        name=name,
        object_type_name='device',
        attribute_type=TEXT,
        is_protected=True,
        display_index=display_index,
        min_width=200,
        default_value='A default value',
        select_options='N/A',
        updated_at=DATETIME_MOCK,
    )


def assert_object_attribute(
    execute_airtable_request_mock,
    test_class,
    expected_status_detail,
    expected_amount,
    expected_name,
):
    execute_airtable_request_mock.assert_called_once()
    assert test_class.status_detail == expected_status_detail
    assert ObjectAttributeBlueprint.objects.count() == expected_amount
    assert ObjectAttributeBlueprint.objects.get(name=expected_name)


@pytest.fixture()
def object_attribute_mock():
    return create_object_attribute('1', 'Object Attribute 001', 1)


@pytest.fixture()
def object_attribute_mock_2():
    return create_object_attribute('2', 'Object Attribute 002', 2)


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: 'Epic',
                TYPE_NAME: 'change_request',
                ATTRIBUTE_TYPE: TEXT,
                MIN_WIDTH: 200,
                DISPLAY_INDEX: 1,
                IS_PROTECTED: True,
                DEFAULT_VALUE: 'Others',
                SELECT_OPTIONS: 'Encrypted,Not encrypted,N/A',
                LAST_MODIFIED: '2022-03-02T22:20:15.000Z',
            },
        }
    ],
)
def test_airtable_sync_create_object_attribute_blueprint(
    execute_airtable_request_mock, graphql_user
):
    expected_status_detail = ['Record created successfully: Epic']
    expected_amount_of_object_attributes = 1
    expected_object_attribute_name = 'Epic'

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    airtable_class_mock.update_blueprint(blueprint_base.update_or_create_object)

    assert_object_attribute(
        execute_airtable_request_mock,
        airtable_class_mock,
        expected_status_detail,
        expected_amount_of_object_attributes,
        expected_object_attribute_name,
    )


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: 'Project',
                DISPLAY_INDEX: 2,
                TYPE_NAME: 'device',
                ATTRIBUTE_TYPE: TEXT,
                MIN_WIDTH: 100,
                IS_PROTECTED: False,
                DEFAULT_VALUE: 'Test value',
                SELECT_OPTIONS: 'Not encrypted,N/A',
                LAST_MODIFIED: '2022-03-02T22:20:15.000Z',
            },
        }
    ],
)
def test_airtable_init_update_object_attribute_unit(
    execute_airtable_request_mock, graphql_user
):
    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    assert not blueprint_base.init_update(None)
    assert blueprint_base.init_update(airtable_class_mock)
    execute_airtable_request_mock.assert_called_once()


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                REFERENCE_ID: '3',
                NAME: 'Model',
                DISPLAY_INDEX: 2,
                TYPE_NAME: 'device',
                ATTRIBUTE_TYPE: TEXT,
                MIN_WIDTH: 200,
                IS_PROTECTED: True,
                DEFAULT_VALUE: 'Default text',
                SELECT_OPTIONS: 'Encrypted',
                LAST_MODIFIED: '2022-03-02T22:20:15.000Z',
            },
        }
    ],
)
def test_airtable_sync_delete_object_attribute_blueprint(
    execute_airtable_request_mock, graphql_user, object_attribute_mock
):
    expected_status_detail = [
        'Record created successfully: Model',
        "Records deleted: ['Object Attribute 001']",
    ]
    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    expected_amount_of_object_attributes = 1
    expected_object_attribute_name = 'Model'

    assert blueprint_base.init_update(airtable_class_mock)

    assert_object_attribute(
        execute_airtable_request_mock,
        airtable_class_mock,
        expected_status_detail,
        expected_amount_of_object_attributes,
        expected_object_attribute_name,
    )


@pytest.mark.django_db
def test_airtable_sync_delete_object_attribute_unit(
    graphql_user, object_attribute_mock, object_attribute_mock_2
):
    object_attributes_to_exclude = [{REFERENCE_ID: '2'}, {REFERENCE_ID: '4'}]
    object_attributes_deleted = get_blueprint_admin_mock().delete_objects(
        object_attributes_to_exclude, graphql_user
    )
    assert len(object_attributes_deleted) == 1
    assert object_attributes_deleted == ['Object Attribute 001']


def get_and_assert_base_mock_classes(
    graphql_user: User,
) -> Tuple[BlueprintAdmin, AirtableSync]:
    blueprint_base = get_blueprint_admin_mock()
    assert blueprint_base

    airtable_class_mock = get_airtable_sync_class(
        graphql_user, OBJECT_ATTRIBUTE_REQUIRED_FIELDS
    )
    assert airtable_class_mock

    return blueprint_base, airtable_class_mock


def get_blueprint_admin_mock():
    return ObjectAttributeBlueprintAdmin(
        model=ObjectAttributeBlueprint, admin_site=AdminSite()
    )

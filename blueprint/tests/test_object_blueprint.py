from typing import Tuple
from unittest.mock import patch

import pytest
from django.contrib.admin import AdminSite

from blueprint.admin import ObjectBlueprintAdmin
from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.commons import AirtableSync
from blueprint.constants import (
    COLOR,
    DESCRIPTION,
    DISPLAY_INDEX,
    ICON,
    IS_SYSTEM_TYPE,
    LAST_MODIFIED,
    NAME,
    OBJECT_REQUIRED_FIELDS,
    TYPE,
)
from blueprint.models.object import ObjectBlueprint
from blueprint.tests.test_commons import (
    DATETIME_MOCK,
    RECORD_ID_MOCK,
    get_airtable_sync_class,
)
from user.models import User


def create_object(name, display_index):
    return ObjectBlueprint.objects.get_or_create(
        display_name=name,
        is_system_type=True,
        description='Some description',
        type_name='device',
        color='purple',
        icon_name='business',
        display_index=display_index,
        updated_at=DATETIME_MOCK,
    )


def assert_object(
    execute_airtable_request_mock,
    test_class,
    expected_status_detail,
    expected_amount,
    expected_name,
):
    execute_airtable_request_mock.assert_called_once()
    assert test_class.status_detail == expected_status_detail
    assert ObjectBlueprint.objects.count() == expected_amount
    assert ObjectBlueprint.objects.get(display_name=expected_name)


@pytest.fixture()
def object_mock():
    return create_object('Object 001', 1)


@pytest.fixture()
def object_mock_2():
    return create_object('Object 002', 2)


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: 'Account',
                TYPE: 'account',
                COLOR: 'purple',
                ICON: 'business',
                DISPLAY_INDEX: 1,
                IS_SYSTEM_TYPE: True,
                DESCRIPTION: 'Any description',
                LAST_MODIFIED: '2022-03-02T22:20:15.000Z',
            },
        }
    ],
)
def test_airtable_sync_create_object_blueprint(
    execute_airtable_request_mock, graphql_user
):
    expected_status_detail = ['Record created successfully: Account']
    expected_amount_of_objects = 1
    expected_object_name = 'Account'

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    airtable_class_mock.update_blueprint(blueprint_base.update_or_create_object)

    assert_object(
        execute_airtable_request_mock,
        airtable_class_mock,
        expected_status_detail,
        expected_amount_of_objects,
        expected_object_name,
    )


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: 'Account',
                TYPE: 'account',
                COLOR: 'purple',
                ICON: 'business',
                DISPLAY_INDEX: 1,
                IS_SYSTEM_TYPE: True,
                DESCRIPTION: 'Any description',
                LAST_MODIFIED: '2022-03-02T22:20:15.000Z',
            },
        }
    ],
)
def test_airtable_init_update_object_unit(execute_airtable_request_mock, graphql_user):
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
                NAME: 'Device',
                TYPE: 'device',
                COLOR: 'red',
                ICON: 'assignment_late',
                DISPLAY_INDEX: 2,
                IS_SYSTEM_TYPE: True,
                DESCRIPTION: 'New object',
                LAST_MODIFIED: '2022-03-02T22:20:15.000Z',
            },
        }
    ],
)
def test_airtable_sync_delete_object_blueprint(
    execute_airtable_request_mock, graphql_user, object_mock
):
    expected_status_detail = [
        'Record created successfully: Device',
        "Records deleted: ['Object 001']",
    ]
    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    expected_amount_of_objects = 1
    expected_object_name = 'Device'

    assert blueprint_base.init_update(airtable_class_mock)

    assert_object(
        execute_airtable_request_mock,
        airtable_class_mock,
        expected_status_detail,
        expected_amount_of_objects,
        expected_object_name,
    )


@pytest.mark.django_db
def test_airtable_sync_delete_object_unit(graphql_user, object_mock, object_mock_2):
    objects_to_exclude = [{NAME: 'Object 002'}, {NAME: 'Object 004'}]
    objects_deleted = get_blueprint_admin_mock().delete_objects(
        objects_to_exclude, graphql_user
    )
    assert len(objects_deleted) == 1
    assert objects_deleted == ['Object 001']


def get_and_assert_base_mock_classes(
    graphql_user: User,
) -> Tuple[BlueprintAdmin, AirtableSync]:
    blueprint_base = get_blueprint_admin_mock()
    assert blueprint_base

    airtable_class_mock = get_airtable_sync_class(graphql_user, OBJECT_REQUIRED_FIELDS)
    assert airtable_class_mock

    return blueprint_base, airtable_class_mock


def get_blueprint_admin_mock():
    return ObjectBlueprintAdmin(model=ObjectBlueprint, admin_site=AdminSite())

from typing import Tuple
from unittest.mock import patch

import pytest
from django.contrib.admin import AdminSite

from blueprint.admin import ControlGroupBlueprintAdmin
from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.commons import AirtableSync
from blueprint.constants import (
    GROUP_REQUIRED_FIELDS,
    LAST_MODIFIED,
    NAME,
    REFERENCE_ID,
    SORT_ORDER,
)
from blueprint.models import ControlGroupBlueprint
from blueprint.tests.test_commons import (
    DATETIME_MOCK,
    RECORD_ID_MOCK,
    get_airtable_sync_class,
)
from user.models import User

LAST_MODIFIED_VALUE = '2022-03-01T23:19:58.000Z'
GROUP_001 = 'Group 001'
GROUP_002 = 'Group 002'
GROUP_003 = 'Group 003'
UPDATE_GROUPS_MOCK = [
    {
        'id': RECORD_ID_MOCK,
        'fields': {
            NAME: GROUP_001,
            REFERENCE_ID: 'GRP-001',
            SORT_ORDER: 1,
            LAST_MODIFIED: LAST_MODIFIED_VALUE,
        },
    },
    {
        'id': RECORD_ID_MOCK,
        'fields': {
            NAME: 'Group 002 [updated name]',
            REFERENCE_ID: 'GRP-002',
            SORT_ORDER: 2,
            LAST_MODIFIED: LAST_MODIFIED_VALUE,
        },
    },
    {
        'id': RECORD_ID_MOCK,
        'fields': {
            NAME: 'Group 003',
            REFERENCE_ID: 'GRP-003',
            SORT_ORDER: 3,
            LAST_MODIFIED: LAST_MODIFIED_VALUE,
        },
    },
]


def create_group(reference_id: str, defaults: dict):
    ControlGroupBlueprint.objects.get_or_create(
        reference_id=reference_id, defaults=defaults
    )


@pytest.fixture()
def group_001():
    create_group(
        reference_id='GRP-001',
        defaults={'name': GROUP_001, 'sort_order': 1, 'updated_at': DATETIME_MOCK},
    )


@pytest.fixture()
def group_002():
    create_group(
        reference_id='GRP-002',
        defaults={
            'name': GROUP_002,
            'sort_order': 2,
            'updated_at': LAST_MODIFIED_VALUE,
        },
    )


@pytest.fixture()
def group_003():
    create_group(
        reference_id='GRP-003',
        defaults={'name': GROUP_003, 'sort_order': 3, 'updated_at': DATETIME_MOCK},
    )


@pytest.mark.django_db
@patch('blueprint.commons.execute_airtable_request', return_value=UPDATE_GROUPS_MOCK)
def test_airtable_sync_update_group_blueprint(
    execute_airtable_request_mock, graphql_user, group_001, group_002
):
    expected_status_detail = ['Record created successfully: Group 003']

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    airtable_class_mock.update_blueprint(blueprint_base.update_or_create_object)
    execute_airtable_request_mock.assert_called_once()
    assert airtable_class_mock.status_detail == expected_status_detail
    assert ControlGroupBlueprint.objects.count() == 3
    assert ControlGroupBlueprint.objects.get(name=GROUP_001)
    assert ControlGroupBlueprint.objects.get(name=GROUP_001).updated_at == DATETIME_MOCK

    assert (
        ControlGroupBlueprint.objects.get(reference_id='GRP-002').name
        != 'Group 002 [updated name]'
    )


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: 'Group 001',
                REFERENCE_ID: 'GRP-001',
                SORT_ORDER: 1,
                LAST_MODIFIED: LAST_MODIFIED_VALUE,
            },
        }
    ],
)
def test_airtable_sync_delete_group_blueprint(
    execute_airtable_request_mock, graphql_user, group_002
):
    expected_status_detail = [
        'Record created successfully: Group 001',
        "Records deleted: ['Group 002']",
    ]

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    assert blueprint_base.init_update(airtable_class_mock)
    execute_airtable_request_mock.assert_called_once()
    assert airtable_class_mock.status_detail == expected_status_detail
    assert ControlGroupBlueprint.objects.count() == 1
    assert ControlGroupBlueprint.objects.get(name='Group 001')


@pytest.mark.django_db
def test_airtable_sync_delete_group_unit(graphql_user, group_002, group_003):
    # Notice GRP-004 does not exist in db, and it is not created because
    # it is being executed only "delete_objects"
    objects_to_exclude = [{REFERENCE_ID: 'GRP-003'}, {REFERENCE_ID: 'GRP-004'}]

    objects_deleted = get_blueprint_admin_mock().delete_objects(
        objects_to_exclude, graphql_user
    )

    assert ControlGroupBlueprint.objects.count() == 1
    assert objects_deleted == [GROUP_002]


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: GROUP_001,
                REFERENCE_ID: 'GRP-001',
                SORT_ORDER: 1,
                LAST_MODIFIED: LAST_MODIFIED_VALUE,
            },
        }
    ],
)
@pytest.mark.django_db
def test_airtable_init_update_groups_unit(execute_airtable_request_mock, graphql_user):
    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    assert not blueprint_base.init_update(None)
    assert blueprint_base.init_update(airtable_class_mock)
    execute_airtable_request_mock.assert_called_once()


def get_and_assert_base_mock_classes(
    graphql_user: User,
) -> Tuple[BlueprintAdmin, AirtableSync]:
    blueprint_base = get_blueprint_admin_mock()
    assert blueprint_base

    airtable_class_mock = get_airtable_sync_class(graphql_user, GROUP_REQUIRED_FIELDS)
    assert airtable_class_mock

    return blueprint_base, airtable_class_mock


def get_blueprint_admin_mock():
    return ControlGroupBlueprintAdmin(
        model=ControlGroupBlueprint, admin_site=AdminSite()
    )

from typing import Tuple
from unittest.mock import patch

import pytest
from django.contrib.admin import AdminSite

from blueprint.admin import TagBlueprintAdmin
from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.commons import AirtableSync
from blueprint.constants import LAST_MODIFIED, NAME, TAG_REQUIRED_FIELDS
from blueprint.models import TagBlueprint
from blueprint.tests.test_commons import (
    DATETIME_MOCK,
    DATETIME_MOCK_2,
    RECORD_ID_MOCK,
    get_airtable_sync_class,
)
from user.models import User

TAG_001 = 'Tag 001'
TAG_002 = 'Tag 002'


def create_tag(name, date):
    return TagBlueprint.objects.get_or_create(name=name, updated_at=date)


@pytest.fixture()
def tag():
    return create_tag(TAG_001, DATETIME_MOCK)


@pytest.fixture()
def tag_2():
    return create_tag('Another tag', DATETIME_MOCK_2)


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: TAG_001,
                LAST_MODIFIED: '2022-03-01T23:19:58.000Z',  # lower than
            },
        },
        {
            'id': RECORD_ID_MOCK,
            'fields': {NAME: TAG_002, LAST_MODIFIED: '2022-03-01T23:19:58.000Z'},
        },
        {
            'id': RECORD_ID_MOCK,
            'fields': {NAME: 'Tag 003', LAST_MODIFIED: '2022-03-01T23:19:58.000Z'},
        },
    ],
)
def test_airtable_sync_update_tag_blueprint(
    execute_airtable_request_mock, graphql_user, tag, tag_2
):
    expected_status_detail = [
        'Record created successfully: Tag 002',
        'Record created successfully: Tag 003',
    ]

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    airtable_class_mock.update_blueprint(blueprint_base.update_or_create_object)

    execute_airtable_request_mock.assert_called_once()
    assert airtable_class_mock.status_detail == expected_status_detail
    assert TagBlueprint.objects.count() == 4
    assert TagBlueprint.objects.get(name=TAG_001)
    assert TagBlueprint.objects.get(name=TAG_001).updated_at == DATETIME_MOCK
    assert TagBlueprint.objects.get(name=TAG_002)


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {NAME: 'New tag', LAST_MODIFIED: '2022-03-01T23:19:58.000Z'},
        }
    ],
)
def test_airtable_sync_delete_tag_blueprint(
    execute_airtable_request_mock, graphql_user, tag
):
    expected_status_detail = [
        'Record created successfully: New tag',
        "Records deleted: ['Tag 001']",
    ]

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    assert blueprint_base.init_update(airtable_class_mock)
    execute_airtable_request_mock.assert_called_once()
    assert airtable_class_mock.status_detail == expected_status_detail
    assert TagBlueprint.objects.count() == 1
    assert TagBlueprint.objects.get(name='New tag')


@pytest.mark.django_db
def test_airtable_sync_delete_tag_unit(graphql_user, tag, tag_2):
    objects_to_exclude = [{NAME: 'Another tag'}, {NAME: 'Tag 004'}]

    objects_deleted = get_blueprint_admin_mock().delete_objects(
        objects_to_exclude, graphql_user
    )
    assert len(objects_deleted) == 1
    assert objects_deleted == [TAG_001]


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {NAME: 'New tag', LAST_MODIFIED: '2022-03-01T23:19:58.000Z'},
        }
    ],
)
def test_airtable_init_update_tag_unit(execute_airtable_request_mock, graphql_user):
    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    assert not blueprint_base.init_update(None)
    assert blueprint_base.init_update(airtable_class_mock)
    execute_airtable_request_mock.assert_called_once()


def get_and_assert_base_mock_classes(
    graphql_user: User,
) -> Tuple[BlueprintAdmin, AirtableSync]:
    blueprint_base = get_blueprint_admin_mock()
    assert blueprint_base

    airtable_class_mock = get_airtable_sync_class(graphql_user, TAG_REQUIRED_FIELDS)
    assert airtable_class_mock

    return blueprint_base, airtable_class_mock


def get_blueprint_admin_mock():
    return TagBlueprintAdmin(model=TagBlueprint, admin_site=AdminSite())

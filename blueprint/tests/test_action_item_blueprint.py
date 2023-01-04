from datetime import datetime
from typing import Tuple
from unittest.mock import patch

import pytest
from django.contrib.admin import AdminSite

from blueprint.admin.action_item import ActionItemBlueprintAdmin, set_action_item_tags
from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.commons import AirtableSync
from blueprint.constants import (
    ACTION_ITEM_REQUIRED_FIELDS,
    CONTROL_REFERENCE_ID,
    DESCRIPTION,
    IS_REQUIRED,
    LAST_MODIFIED,
    NAME,
    RECURRENT_SCHEDULE,
    REFERENCE_ID,
    REQUIRES_EVIDENCE,
    SORT_ORDER,
    SUGGESTED_OWNER,
)
from blueprint.models import (
    ActionItemBlueprint,
    ControlBlueprint,
    ControlFamilyBlueprint,
    TagBlueprint,
)
from blueprint.tests.test_commons import (
    CONTROL_FAMILY_AIRTABLE_ID,
    DATETIME_MOCK_2,
    RECORD_ID_MOCK,
    get_airtable_sync_class,
)
from user.models import User

LAST_MODIFIED_VALUE = '2022-03-01T23:19:58.000Z'
DATETIME_MOCK = datetime.strptime('2022-04-02T22:17:21.000Z', '%Y-%m-%dT%H:%M:%S.%f%z')
ACTION_ITEM_001_NO_CHANGE = 'Action Item 001 [No change]'
ACTION_ITEM_002 = 'Action Item 002'
ACTION_ITEM_003 = 'Action Item 003'
DEFAULT_DISPLAY_ID = 9999999
ACTION_ITEM_001_AIRTABLE_MOCK = {
    'id': RECORD_ID_MOCK,
    'fields': {
        NAME: 'Action Item 001',
        REFERENCE_ID: 'AC-S-001',
        DESCRIPTION: 'Action Item test description',
        CONTROL_REFERENCE_ID: ['AC-01'],
        SORT_ORDER: 1,
        LAST_MODIFIED: LAST_MODIFIED_VALUE,
    },
}
ACTION_ITEM_002_AIRTABLE_MOCK = {
    'id': RECORD_ID_MOCK,
    'fields': {
        NAME: ACTION_ITEM_002,
        REFERENCE_ID: 'AC-S-002',
        DESCRIPTION: 'Action Item test description 2',
        CONTROL_REFERENCE_ID: ['AC-01'],
        SORT_ORDER: 33,
        LAST_MODIFIED: LAST_MODIFIED_VALUE,
    },
}
ACTION_ITEM_003_AIRTABLE_MOCK = {
    'id': RECORD_ID_MOCK,
    'fields': {
        NAME: ACTION_ITEM_003,
        REFERENCE_ID: 'AC-S-003',
        DESCRIPTION: 'Action Item test description 3',
        CONTROL_REFERENCE_ID: ['AC-01'],
        SORT_ORDER: 'string wrong value',
        LAST_MODIFIED: LAST_MODIFIED_VALUE,
    },
}


@pytest.fixture()
def control_asset_inventory():
    ControlBlueprint.objects.get_or_create(
        airtable_record_id=RECORD_ID_MOCK,
        defaults={
            'name': 'Asset Inventory',
            'reference_id': 'AC-01',
            'description': 'Any description',
            'family': ControlFamilyBlueprint.objects.create(
                airtable_record_id=CONTROL_FAMILY_AIRTABLE_ID,
                name='Family 1',
                acronym='FA',
            ),
            'updated_at': datetime.strptime(
                '2022-03-02T22:20:15.000Z', '%Y-%m-%dT%H:%M:%S.%f%z'
            ),
        },
    )


@pytest.fixture()
def action_item_001():
    ActionItemBlueprint.objects.get_or_create(
        airtable_record_id=RECORD_ID_MOCK,
        name=ACTION_ITEM_001_NO_CHANGE,
        reference_id='AC-S-001',
        description='Description for action item 001',
        updated_at=DATETIME_MOCK_2,
    )


@pytest.fixture()
def action_item_002():
    ActionItemBlueprint.objects.get_or_create(
        airtable_record_id=RECORD_ID_MOCK,
        name=ACTION_ITEM_002,
        reference_id='AC-S-002',
        description='Description for action item 002',
        updated_at=DATETIME_MOCK_2,
    )


@pytest.fixture()
def action_item_003():
    ActionItemBlueprint.objects.get_or_create(
        airtable_record_id=RECORD_ID_MOCK,
        name=ACTION_ITEM_003,
        reference_id='AC-S-003',
        description='Description for action item 003',
        updated_at=DATETIME_MOCK_2,
    )


def create_tag(name, airtable_id, date):
    return TagBlueprint.objects.get_or_create(
        name=name, airtable_record_id=airtable_id, updated_at=date
    )


@pytest.fixture()
def tag_001():
    return create_tag('Tag 001', '1234tag', DATETIME_MOCK)


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        ACTION_ITEM_001_AIRTABLE_MOCK,
        ACTION_ITEM_002_AIRTABLE_MOCK,
        ACTION_ITEM_003_AIRTABLE_MOCK,
    ],
)
def test_airtable_sync_update_action_item_blueprint(
    execute_airtable_request_mock,
    graphql_user,
    control_asset_inventory,
    action_item_001,
):
    expected_status_detail = [
        'Record created successfully: Action Item 002',
        'Record created successfully: Action Item 003',
    ]

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    airtable_class_mock.update_blueprint(blueprint_base.update_or_create_object)

    execute_airtable_request_mock.assert_called_once()
    assert airtable_class_mock.status_detail == expected_status_detail
    assert ActionItemBlueprint.objects.count() == 3
    assert ActionItemBlueprint.objects.get(name=ACTION_ITEM_003)

    action_item = ActionItemBlueprint.objects.get(name=ACTION_ITEM_003)
    assert action_item.controls_blueprint.count() == 1
    assert action_item.controls_blueprint.get(reference_id='AC-01')
    assert action_item.display_id == DEFAULT_DISPLAY_ID

    action_item_without_update = ActionItemBlueprint.objects.get(
        reference_id='AC-S-001'
    )
    assert action_item_without_update.name == ACTION_ITEM_001_NO_CHANGE

    assert (
        ActionItemBlueprint.objects.get(name=ACTION_ITEM_002).display_id
        == ACTION_ITEM_002_AIRTABLE_MOCK['fields'][SORT_ORDER]
    )


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[ACTION_ITEM_001_AIRTABLE_MOCK],
)
def test_airtable_sync_delete_action_item_blueprint(
    execute_airtable_request_mock,
    graphql_user,
    control_asset_inventory,
    action_item_002,
):
    expected_status_detail = [
        'Record created successfully: Action Item 001',
        "Records deleted: ['Action Item 002']",
    ]

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    assert blueprint_base.init_update(airtable_class_mock)
    execute_airtable_request_mock.assert_called_once()
    assert airtable_class_mock.status_detail == expected_status_detail
    assert ActionItemBlueprint.objects.count() == 1
    assert ActionItemBlueprint.objects.get(name='Action Item 001')


@pytest.mark.django_db
def test_airtable_sync_delete_action_item_unit(
    graphql_user, action_item_001, action_item_002, action_item_003
):
    objects_to_exclude = [{REFERENCE_ID: 'AC-S-001'}]

    objects_deleted = get_blueprint_admin_mock().delete_objects(
        objects_to_exclude, graphql_user
    )

    print('DELETED:', objects_deleted)
    assert len(objects_deleted) == 2
    assert objects_deleted == [ACTION_ITEM_002, ACTION_ITEM_003]


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[ACTION_ITEM_001_AIRTABLE_MOCK],
)
def test_airtable_init_update_action_items_unit(
    execute_airtable_request_mock, graphql_user
):
    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    assert not blueprint_base.init_update(None)
    assert blueprint_base.init_update(airtable_class_mock)
    execute_airtable_request_mock.assert_called_once()


@pytest.mark.django_db
def test_get_default_fields(graphql_user):
    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    fields = {
        NAME: 'Action Item 1',
        DESCRIPTION: 'Description for action item 1',
        IS_REQUIRED: True,
        SUGGESTED_OWNER: ['1234owner'],
        RECURRENT_SCHEDULE: 'annually',
        REQUIRES_EVIDENCE: 'Yes',
        SORT_ORDER: 5,
    }

    related_records = {'1234owner': {NAME: 'Technical'}}

    default_fields = blueprint_base.get_default_fields(fields, related_records)
    assert default_fields.get('name') == 'Action Item 1'
    assert default_fields.get('description') == '<p>Description for action item 1</p>'
    assert default_fields.get('suggested_owner') == 'Technical'
    assert default_fields.get('recurrent_schedule') == 'annually'
    assert default_fields.get('is_required') is not True
    assert default_fields.get('is_recurrent') is True
    assert default_fields.get('requires_evidence') is True
    assert default_fields.get('display_id') == 5


@pytest.mark.django_db
def test_set_action_item_tags(action_item_001, tag_001):
    fields = {'Tags': ['1234tag']}
    action_item = ActionItemBlueprint.objects.all().first()
    set_action_item_tags(action_item, fields)
    ai_tags = action_item.tags.all()

    assert ai_tags[0].name == 'Tag 001'
    assert len(ai_tags) == 1


def get_and_assert_base_mock_classes(
    graphql_user: User,
) -> Tuple[BlueprintAdmin, AirtableSync]:
    blueprint_base = get_blueprint_admin_mock()
    assert blueprint_base

    airtable_class_mock = get_airtable_sync_class(
        graphql_user, ACTION_ITEM_REQUIRED_FIELDS
    )
    assert airtable_class_mock

    return blueprint_base, airtable_class_mock


def get_blueprint_admin_mock():
    return ActionItemBlueprintAdmin(model=ActionItemBlueprint, admin_site=AdminSite())

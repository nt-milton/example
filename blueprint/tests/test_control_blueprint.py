from typing import Tuple
from unittest.mock import patch

import pytest
from django.contrib.admin import AdminSite

from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.admin.control import ControlBlueprintAdmin
from blueprint.commons import AirtableSync
from blueprint.constants import (
    CONTROL_FAMILY_REFERENCES,
    CONTROL_REQUIRED_FIELDS,
    DESCRIPTION,
    FRAMEWORK_TAG,
    GROUP_REFERENCE_ID,
    HOUSEHOLD,
    LAST_MODIFIED,
    NAME,
    REFERENCE_ID,
    SORT_ORDER_WITHIN_GROUP,
    STATUS,
    SUGGESTED_OWNER,
)
from blueprint.models import ControlBlueprint, ControlFamilyBlueprint
from blueprint.tests.test_commons import (
    CONTROL_FAMILY_AIRTABLE_ID,
    RECORD_ID_MOCK,
    get_airtable_sync_class,
)
from user.models import User

ASSET_INVENTORY = 'Asset Inventory'
LAST_MODIFIED_VALUE = '2022-03-02T22:20:15.000Z'
CONTROL_FAMILY_NAME = 'Family 1'


@pytest.fixture()
def family_001():
    ControlFamilyBlueprint.objects.get_or_create(
        airtable_record_id=CONTROL_FAMILY_AIRTABLE_ID,
        name=CONTROL_FAMILY_NAME,
        acronym='FA',
    )


@pytest.fixture()
def control_asset_inventory():
    ControlBlueprint.objects.create(
        name=ASSET_INVENTORY,
        reference_id='CTF-001 (ISO)',
        airtable_record_id=CONTROL_FAMILY_AIRTABLE_ID,
        description='Any description',
        updated_at=LAST_MODIFIED_VALUE,
    )


@pytest.fixture()
def control_asset_inventory_002():
    ControlBlueprint.objects.create(
        name='Asset Inventory 2',
        reference_id='CTF-002',
        airtable_record_id=CONTROL_FAMILY_AIRTABLE_ID,
        description='My description',
        updated_at=LAST_MODIFIED_VALUE,
    )


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: ASSET_INVENTORY,
                REFERENCE_ID: 'CTF-001 (ISO)',
                HOUSEHOLD: 'CTF-001',
                FRAMEWORK_TAG: ['12345D'],
                SUGGESTED_OWNER: ['12346D'],
                CONTROL_FAMILY_REFERENCES: CONTROL_FAMILY_NAME,
                DESCRIPTION: 'Any description',
                STATUS: 'Not Implemented',
                GROUP_REFERENCE_ID: [],
                LAST_MODIFIED: '2022-03-02T22:20:15.000Z',
                SORT_ORDER_WITHIN_GROUP: '2',
            },
        }
    ],
)
def test_airtable_sync_create_control_blueprint(
    execute_airtable_request_mock, graphql_user, family_001
):
    expected_status_detail = ['Record created successfully: Asset Inventory']
    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    airtable_class_mock.related_table_records = {
        'framework_tags': {'12345D': {NAME: 'ISO'}},
        'roles': {'12346D': {NAME: 'Technical'}},
    }

    airtable_class_mock.update_blueprint(blueprint_base.update_or_create_object)

    execute_airtable_request_mock.assert_called_once()
    assert airtable_class_mock.status_detail == expected_status_detail
    assert ControlBlueprint.objects.count() == 1
    assert ControlBlueprint.objects.get(name=ASSET_INVENTORY)


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: 'Asset Inventory UPDATED',
                REFERENCE_ID: 'CTF-001 (ISO)',
                HOUSEHOLD: 'CTF-001',
                FRAMEWORK_TAG: ['12345D'],
                SUGGESTED_OWNER: ['12346D'],
                CONTROL_FAMILY_REFERENCES: CONTROL_FAMILY_NAME,
                DESCRIPTION: 'Any description',
                STATUS: 'Not Implemented',
                GROUP_REFERENCE_ID: [],
                LAST_MODIFIED: '2022-04-02T22:20:15.000Z',
                SORT_ORDER_WITHIN_GROUP: '2',
            },
        }
    ],
)
def test_airtable_sync_update_control_blueprint(
    execute_airtable_request_mock, graphql_user, family_001, control_asset_inventory
):
    expected_status_detail = ['Record updated successfully: Asset Inventory UPDATED']

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    airtable_class_mock.related_table_records = {
        'framework_tags': {'12345D': {NAME: 'ISO'}},
        'roles': {'12346D': {NAME: 'Technical'}},
    }

    airtable_class_mock.update_blueprint(blueprint_base.update_or_create_object)

    execute_airtable_request_mock.assert_called_once()
    assert airtable_class_mock.status_detail == expected_status_detail
    assert ControlBlueprint.objects.count() == 1
    assert ControlBlueprint.objects.get(name='Asset Inventory UPDATED')


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: ASSET_INVENTORY,
                REFERENCE_ID: 'CTF-001 (SOC)',
                HOUSEHOLD: 'CTF-001',
                FRAMEWORK_TAG: ['12345D'],
                SUGGESTED_OWNER: ['12346D'],
                CONTROL_FAMILY_REFERENCES: CONTROL_FAMILY_NAME,
                DESCRIPTION: 'Any description',
                STATUS: 'Not Implemented',
                GROUP_REFERENCE_ID: [],
                LAST_MODIFIED: '2022-04-02T22:20:15.000Z',
                SORT_ORDER_WITHIN_GROUP: '2',
            },
        }
    ],
)
def test_airtable_sync_delete_control_blueprint(
    execute_airtable_request_mock, graphql_user, family_001, control_asset_inventory_002
):
    expected_status_detail = "Records deleted: ['Asset Inventory 2']"

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    airtable_class_mock.related_table_records = {
        'framework_tags': {'12345D': {NAME: 'ISO'}},
        'roles': {'12346D': {NAME: 'Technical'}},
    }

    assert blueprint_base.init_update(airtable_class_mock)
    execute_airtable_request_mock.assert_called_once()
    assert airtable_class_mock.status_detail[1] == expected_status_detail
    assert ControlBlueprint.objects.count() == 1
    assert ControlBlueprint.objects.get(name=ASSET_INVENTORY)


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: ASSET_INVENTORY,
                REFERENCE_ID: 'CTF-001 (HIPPA)',
                HOUSEHOLD: 'CTF-001',
                FRAMEWORK_TAG: ['12345D'],
                SUGGESTED_OWNER: ['12346D'],
                CONTROL_FAMILY_REFERENCES: CONTROL_FAMILY_NAME,
                DESCRIPTION: 'Any description',
                STATUS: 'Not Implemented',
                GROUP_REFERENCE_ID: [],
                LAST_MODIFIED: '2022-04-02T22:20:15.000Z',
            },
        }
    ],
)
def test_airtable_init_update_control_unit(execute_airtable_request_mock, graphql_user):
    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    assert not blueprint_base.init_update(None)
    assert blueprint_base.init_update(airtable_class_mock)
    execute_airtable_request_mock.assert_called_once()


@pytest.mark.django_db
def test_get_default_fields(graphql_user, family_001):
    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    fields = {
        NAME: ASSET_INVENTORY,
        HOUSEHOLD: 'CTF-002',
        FRAMEWORK_TAG: ['12347D'],
        SUGGESTED_OWNER: ['12346D'],
        DESCRIPTION: 'Any description',
        'Status': 'Not Implemented',
        CONTROL_FAMILY_REFERENCES: CONTROL_FAMILY_NAME,
    }

    related_records = {
        'framework_tags': {'12347D': {NAME: 'SOC-A'}},
        'roles': {'12346D': {NAME: 'Technical'}},
    }

    default_fields = blueprint_base.get_default_fields(fields, related_records)
    assert default_fields.get('name') == ASSET_INVENTORY
    assert default_fields.get('framework_tag') == 'SOC-A'
    assert default_fields.get('suggested_owner') == 'Technical'
    assert default_fields.get('household') == 'CTF-002'
    assert default_fields.get('family')
    assert default_fields.get('family') == ControlFamilyBlueprint.objects.get(
        name=CONTROL_FAMILY_NAME
    )


def get_and_assert_base_mock_classes(
    graphql_user: User,
) -> Tuple[BlueprintAdmin, AirtableSync]:
    blueprint_base = get_blueprint_admin_mock()
    assert blueprint_base

    airtable_class_mock = get_airtable_sync_class(graphql_user, CONTROL_REQUIRED_FIELDS)
    assert airtable_class_mock

    return blueprint_base, airtable_class_mock


def get_blueprint_admin_mock():
    return ControlBlueprintAdmin(model=ControlBlueprint, admin_site=AdminSite())

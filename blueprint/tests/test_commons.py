from datetime import datetime
from typing import Any, Dict, List, Tuple
from unittest.mock import patch

import pytest
from django.http import HttpRequest

from blueprint.admin.page import init_update_all_blueprints
from blueprint.commons import AirtableSync
from blueprint.constants import (
    CONTROL_FAMILY_REFERENCES,
    CONTROL_REQUIRED_FIELDS,
    FRAMEWORK_TAG,
    HOUSEHOLD,
    NAME,
    REFERENCE_ID,
)
from blueprint.models import Page
from blueprint.models.history import BlueprintHistory
from blueprint.prescribe import create_prescription_history_entry_controls_prescribed
from organization.tasks import create_prescription_history
from user.models import User

BLUEPRINT_NAME_TEST = 'blueprint_test'
TABLE_NAME_TEST = 'table_test'
AIRTABLE_API_KEY_TEST = 'my_test_key'
AIRTABLE_BASE_ID = 'my_airtable_link_base'
FRAMEWORK_TAG_ID = '12345D'
RECORD_FIELDS_MOCK = {
    'fields': {
        NAME: 'Control Family 1',
        REFERENCE_ID: 'hola',
        HOUSEHOLD: 'household-test',
        CONTROL_FAMILY_REFERENCES: 'hola',
        FRAMEWORK_TAG: [FRAMEWORK_TAG_ID],
    }
}
RECORD_ID_MOCK = 1234
FORMATTED_RECORD_FIELDS_MOCK = {
    'airtable_record_id': RECORD_ID_MOCK,
    NAME: 'Control Family 1',
    REFERENCE_ID: 'hola',
    HOUSEHOLD: 'household-test',
    CONTROL_FAMILY_REFERENCES: 'hola',
    FRAMEWORK_TAG: [FRAMEWORK_TAG_ID],
}
CONTROL_FAMILY_AIRTABLE_ID = '12345qwerty'
DATETIME_MOCK = datetime.strptime('2022-04-02T22:17:21.000Z', '%Y-%m-%dT%H:%M:%S.%f%z')
DATETIME_MOCK_2 = datetime.strptime(
    '2022-03-01T23:19:58.000Z', '%Y-%m-%dT%H:%M:%S.%f%z'
)
HISTORY_STATUS = 'Successful'


class MockRequest(object):
    def __init__(self, user=None):
        self.user = user

    def add_message(self, message):
        print(message)


def get_airtable_sync_class(
    graphql_user: User, required_fields: List[str]
) -> AirtableSync:
    Page.objects.create(
        name=BLUEPRINT_NAME_TEST,
        airtable_api_key=AIRTABLE_API_KEY_TEST,
        airtable_link=AIRTABLE_BASE_ID,
    )

    related_table_records = {FRAMEWORK_TAG_ID: {NAME: 'SOC'}}

    return AirtableSync(
        table_name=TABLE_NAME_TEST,
        blueprint_name=BLUEPRINT_NAME_TEST,
        required_fields=required_fields,
        request_user=graphql_user,
        related_table_records=related_table_records,
    )


@pytest.mark.django_db
def test_airtable_sync_class_creation(graphql_user):
    test_class = get_airtable_sync_class(graphql_user, CONTROL_REQUIRED_FIELDS)

    assert test_class.table_name == TABLE_NAME_TEST
    assert test_class.api_key == AIRTABLE_API_KEY_TEST
    assert test_class.base_id == AIRTABLE_BASE_ID
    assert test_class.required_fields == CONTROL_REQUIRED_FIELDS
    assert test_class.request_user == graphql_user


@pytest.mark.django_db
def test_airtable_sync_are_fields_required_empty(graphql_user):
    test_class = get_airtable_sync_class(graphql_user, CONTROL_REQUIRED_FIELDS)
    assert test_class.are_fields_required_empty({})

    assert test_class.are_fields_required_empty({REFERENCE_ID: 'hola'})

    assert not test_class.are_fields_required_empty(RECORD_FIELDS_MOCK.get('fields'))


@pytest.mark.django_db
def test_airtable_sync_validate_fields(graphql_user):
    test_class = get_airtable_sync_class(graphql_user, CONTROL_REQUIRED_FIELDS)

    assert not test_class.validate_fields({})
    assert not test_class.validate_fields({'id': RECORD_ID_MOCK})
    assert not test_class.validate_fields({'id': RECORD_ID_MOCK, 'fields': {}})
    assert not test_class.validate_fields(
        {'id': RECORD_ID_MOCK, 'fields': {REFERENCE_ID: 'hola'}}
    )

    assert not test_class.validate_fields(
        {'id': RECORD_ID_MOCK, 'fields': {CONTROL_FAMILY_REFERENCES: 'hola'}}
    )

    assert test_class.validate_fields({'id': RECORD_ID_MOCK, **RECORD_FIELDS_MOCK})


@pytest.mark.django_db
def test_airtable_sync_get_record_fields(graphql_user):
    test_class = get_airtable_sync_class(graphql_user, CONTROL_REQUIRED_FIELDS)

    assert not test_class.get_record_fields({})

    assert (
        test_class.get_record_fields({'id': RECORD_ID_MOCK, **RECORD_FIELDS_MOCK})
        == FORMATTED_RECORD_FIELDS_MOCK
    )


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: 'Asset Inventory',
                REFERENCE_ID: 'CTF-001 (ISO)',
                HOUSEHOLD: 'CTF-001',
                FRAMEWORK_TAG: [FRAMEWORK_TAG_ID],
                CONTROL_FAMILY_REFERENCES: [CONTROL_FAMILY_AIRTABLE_ID],
                'Description': 'Any description',
                'Status': 'Not Implemented',
                'Group Reference ID': [],
            },
        },
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: 'Asset Inventory 2',
                REFERENCE_ID: 'CTF-002 (SOC)',
                HOUSEHOLD: 'CTF-002',
                FRAMEWORK_TAG: [FRAMEWORK_TAG_ID],
                CONTROL_FAMILY_REFERENCES: [CONTROL_FAMILY_AIRTABLE_ID],
                'Description': 'Any description',
                'Status': 'Not Implemented',
                'Group Reference ID': [],
            },
        },
    ],
)
def test_airtable_sync_iterate_records(execute_airtable_request_mock, graphql_user):
    status_detail = [
        'Record created successfully: Asset Inventory',
        'Record created successfully: Asset Inventory 2',
    ]
    test_class = get_airtable_sync_class(graphql_user, CONTROL_REQUIRED_FIELDS)

    def upsert_object_mock(
        fields: Dict, _user, _related_table
    ) -> Tuple[Any, bool, bool]:
        return fields.get(NAME), True, False

    test_class.iterate_records(upsert_object_mock)

    execute_airtable_request_mock.assert_called_once()
    assert test_class.status_detail == status_detail


@pytest.mark.django_db
@patch('blueprint.admin.page.init_update_for_any_blueprint')
@patch('blueprint.admin.page.init_update_certifications')
@patch('blueprint.admin.page.get_airtable_sync_class_certifications')
def test_airtable_sync_all_blueprint_unit(
    get_airtable_sync_class_mock,
    init_update_certifications_mock,
    init_update_for_any_blueprint_mock,
    graphql_user,
):
    request = HttpRequest()
    request.user = graphql_user
    init_update_amount = 14

    init_update_all_blueprints(request)
    assert init_update_for_any_blueprint_mock.call_count == init_update_amount
    init_update_certifications_mock.assert_called_once()
    get_airtable_sync_class_mock.assert_called_once()


@pytest.mark.django_db
def test_prescription_history_entry_unit(graphql_organization, graphql_user):
    create_prescription_history(graphql_organization, graphql_user, HISTORY_STATUS)
    expected_content_description = (
        'Default content for all new '
        'organizations, including team charters,'
        ' objects, offboarding checklist, '
        'and trainings.'
    )
    assert BlueprintHistory.objects.count() == 1
    assert BlueprintHistory.objects.get(
        content_description=expected_content_description
    )


@pytest.mark.django_db
def test_controls_prescribed_prescription_history_entry_unit(
    graphql_organization, graphql_user
):
    control_ref_ids = ['AC-01-SOC']
    create_prescription_history_entry_controls_prescribed(
        graphql_organization, graphql_user, control_ref_ids, HISTORY_STATUS
    )
    expected_content_description = '0 Controls prescribed, within the frameworks: '

    assert BlueprintHistory.objects.count() == 1
    assert BlueprintHistory.objects.get(
        content_description=expected_content_description
    )

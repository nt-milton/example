from typing import Tuple
from unittest.mock import patch

import pytest
from django.contrib.admin import AdminSite

from blueprint.admin import ChecklistBlueprintAdmin
from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.commons import AirtableSync
from blueprint.constants import (
    CATEGORY,
    CHECKLIST,
    CHECKLIST_REQUIRED_FIELDS,
    DESCRIPTION,
    LAST_MODIFIED,
    REFERENCE_ID,
    TYPE,
)
from blueprint.models.checklist import ChecklistBlueprint
from blueprint.tests.test_commons import (
    DATETIME_MOCK,
    RECORD_ID_MOCK,
    get_airtable_sync_class,
)
from user.models import User


def create_checklist(reference_id, description):
    return ChecklistBlueprint.objects.get_or_create(
        reference_id=reference_id,
        checklist='Offboarding',
        description=description,
        type='offboarding',
        category='Test category',
        updated_at=DATETIME_MOCK,
    )


def assert_checklist(
    execute_airtable_request_mock,
    test_class,
    expected_status_detail,
    expected_amount,
    expected_description,
):
    execute_airtable_request_mock.assert_called_once()
    assert test_class.status_detail == expected_status_detail
    assert ChecklistBlueprint.objects.count() == expected_amount
    assert ChecklistBlueprint.objects.get(description=expected_description)


@pytest.fixture()
def checklist_mock():
    return create_checklist(1, 'Checklist 001')


@pytest.fixture()
def checklist_mock_2():
    return create_checklist(2, 'Checklist 002')


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                REFERENCE_ID: 1,
                CHECKLIST: 'Offboarding',
                DESCRIPTION: 'Remove employee from e-mail group.',
                TYPE: 'offboarding',
                CATEGORY: 'Compliance',
                LAST_MODIFIED: '2022-03-02T22:20:15.000Z',
            },
        }
    ],
)
def test_airtable_sync_create_checklist_blueprint(
    execute_airtable_request_mock, graphql_user
):
    expected_status_detail = [
        'Record created successfully: Remove employee from e-mail group.'
    ]
    expected_amount_of_checklists = 1
    expected_checklist_description = 'Remove employee from e-mail group.'

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    airtable_class_mock.update_blueprint(blueprint_base.update_or_create_object)

    assert_checklist(
        execute_airtable_request_mock,
        airtable_class_mock,
        expected_status_detail,
        expected_amount_of_checklists,
        expected_checklist_description,
    )


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                REFERENCE_ID: 1,
                CHECKLIST: 'Offboarding',
                DESCRIPTION: 'Remove employee from e-mail group.',
                TYPE: 'offboarding',
                CATEGORY: 'Compliance',
                LAST_MODIFIED: '2022-03-02T22:20:15.000Z',
            },
        }
    ],
)
def test_airtable_init_update_checklist_unit(
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
                REFERENCE_ID: 4,
                CHECKLIST: 'Offboarding',
                DESCRIPTION: 'New checklist',
                TYPE: 'offboarding',
                CATEGORY: 'Compliance',
                LAST_MODIFIED: '2022-03-01T23:19:58.000Z',
            },
        }
    ],
)
def test_airtable_sync_delete_checklist_blueprint(
    execute_airtable_request_mock, graphql_user, checklist_mock
):
    expected_status_detail = [
        'Record created successfully: New checklist',
        "Records deleted: ['Checklist 001']",
    ]
    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    expected_amount_of_checklist = 1
    expected_checklist_description = 'New checklist'

    assert blueprint_base.init_update(airtable_class_mock)

    assert_checklist(
        execute_airtable_request_mock,
        airtable_class_mock,
        expected_status_detail,
        expected_amount_of_checklist,
        expected_checklist_description,
    )


@pytest.mark.django_db
def test_airtable_sync_delete_checklist_unit(
    graphql_user, checklist_mock, checklist_mock_2
):
    objects_to_exclude = [{REFERENCE_ID: 2}, {REFERENCE_ID: 4}]
    objects_deleted = get_blueprint_admin_mock().delete_objects(
        objects_to_exclude, graphql_user
    )
    assert len(objects_deleted) == 1
    assert objects_deleted == ['Checklist 001']


def get_and_assert_base_mock_classes(
    graphql_user: User,
) -> Tuple[BlueprintAdmin, AirtableSync]:
    blueprint_base = get_blueprint_admin_mock()
    assert blueprint_base

    airtable_class_mock = get_airtable_sync_class(
        graphql_user, CHECKLIST_REQUIRED_FIELDS
    )
    assert airtable_class_mock

    return blueprint_base, airtable_class_mock


def get_blueprint_admin_mock():
    return ChecklistBlueprintAdmin(model=ChecklistBlueprint, admin_site=AdminSite())

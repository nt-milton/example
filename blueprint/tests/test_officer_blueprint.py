from typing import Tuple
from unittest.mock import patch

import pytest
from django.contrib.admin import AdminSite

from blueprint.admin import OfficerBlueprintAdmin
from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.commons import AirtableSync
from blueprint.constants import (
    DESCRIPTION,
    LAST_MODIFIED,
    NAME,
    OFFICERS_REQUIRED_FIELDS,
)
from blueprint.models.officer import OfficerBlueprint
from blueprint.tests.test_commons import (
    CONTROL_FAMILY_AIRTABLE_ID,
    DATETIME_MOCK,
    RECORD_ID_MOCK,
    get_airtable_sync_class,
)
from user.models import User


def create_officer(name):
    return OfficerBlueprint.objects.get_or_create(
        name=name, description='Officer description', updated_at=DATETIME_MOCK
    )


@pytest.fixture()
def officer_mock():
    return create_officer('Officer 001')


@pytest.fixture()
def officer_mock_2():
    return create_officer('Officer 002')


@pytest.fixture()
def officer_to_update_mock():
    OfficerBlueprint.objects.create(
        name='IRT Security Officer',
        airtable_record_id=CONTROL_FAMILY_AIRTABLE_ID,
        description='Any description',
        updated_at='2022-03-02T22:20:15.000Z',
    )


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: 'IRT Security Officer',
                DESCRIPTION: 'Any description',
                LAST_MODIFIED: '2022-03-02T22:20:15.000Z',
            },
        },
        {
            'id': 'abcs5s5s',
            'fields': {
                NAME: 'Chief Executive Officer (CEO)',
                DESCRIPTION: 'My description',
                LAST_MODIFIED: '2022-03-01T22:20:15.000Z',
            },
        },
    ],
)
def test_airtable_sync_create_officers_blueprint(
    execute_airtable_request_mock, graphql_user: User
):
    expected_status_detail = [
        'Record created successfully: IRT Security Officer',
        'Record created successfully: Chief Executive Officer (CEO)',
    ]

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    airtable_class_mock.update_blueprint(blueprint_base.update_or_create_object)

    execute_airtable_request_mock.assert_called_once()
    assert airtable_class_mock.status_detail == expected_status_detail
    assert OfficerBlueprint.objects.count() == 2
    assert OfficerBlueprint.objects.get(name='IRT Security Officer')
    assert OfficerBlueprint.objects.get(name='Chief Executive Officer (CEO)')


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: 'IRT Security Officer',
                DESCRIPTION: 'Any description [UPDATED]',
                LAST_MODIFIED: '2022-07-02T22:22:26.000Z',
            },
        }
    ],
)
def test_airtable_sync_update_officer_blueprint(
    execute_airtable_request_mock, graphql_user: User, officer_to_update_mock
):
    expected_status_detail = ['Record updated successfully: IRT Security Officer']

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    airtable_class_mock.update_blueprint(blueprint_base.update_or_create_object)

    execute_airtable_request_mock.assert_called_once()

    assert airtable_class_mock.status_detail == expected_status_detail
    assert OfficerBlueprint.objects.count() == 1
    assert OfficerBlueprint.objects.get(description='Any description [UPDATED]')


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: 'New officer',
                DESCRIPTION: 'Any description',
                LAST_MODIFIED: '2022-03-01T23:19:58.000Z',
            },
        }
    ],
)
def test_airtable_init_update_officers_unit(
    execute_airtable_request_mock, graphql_user: User
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
                NAME: 'New officer',
                DESCRIPTION: 'Any description',
                LAST_MODIFIED: '2022-03-01T23:19:58.000Z',
            },
        }
    ],
)
def test_airtable_sync_delete_officer_blueprint(
    execute_airtable_request_mock, graphql_user: User, officer_mock
):
    expected_status_detail = [
        'Record created successfully: New officer',
        "Records deleted: ['Officer 001']",
    ]

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    assert blueprint_base.init_update(airtable_class_mock)
    execute_airtable_request_mock.assert_called_once()
    assert airtable_class_mock.status_detail == expected_status_detail
    assert OfficerBlueprint.objects.count() == 1
    assert OfficerBlueprint.objects.get(name='New officer')


@pytest.mark.django_db
def test_airtable_sync_delete_officer_unit(
    graphql_user: User, officer_mock, officer_mock_2
):
    officers_to_exclude = [
        {NAME: 'Officer 002', DESCRIPTION: 'Some desc'},
        {NAME: 'Officer 004', DESCRIPTION: 'Another desc'},
    ]

    blueprint_base = get_officer_blueprint_admin_mock()

    officers_deleted = blueprint_base.delete_objects(officers_to_exclude, graphql_user)
    assert len(officers_deleted) == 1
    assert officers_deleted[0] == 'Officer 001'


def get_officer_blueprint_admin_mock() -> BlueprintAdmin:
    return OfficerBlueprintAdmin(model=OfficerBlueprint, admin_site=AdminSite())


def get_airtable_sync_class_mock(graphql_user: User) -> AirtableSync:
    return get_airtable_sync_class(graphql_user, OFFICERS_REQUIRED_FIELDS)


def get_and_assert_base_mock_classes(
    graphql_user: User,
) -> Tuple[BlueprintAdmin, AirtableSync]:
    blueprint_base = get_officer_blueprint_admin_mock()
    assert blueprint_base

    airtable_class_mock = get_airtable_sync_class_mock(graphql_user)
    assert airtable_class_mock

    return blueprint_base, airtable_class_mock

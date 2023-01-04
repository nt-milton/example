from typing import Tuple
from unittest.mock import patch

import pytest
from django.contrib.admin import AdminSite

from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.admin.implementation_guide import ImplementationGuideBlueprintAdmin
from blueprint.commons import AirtableSync
from blueprint.constants import DESCRIPTION, GUIDES_REQUIRED_FIELDS, LAST_MODIFIED, NAME
from blueprint.models import ImplementationGuideBlueprint
from blueprint.tests.test_commons import (
    DATETIME_MOCK,
    RECORD_ID_MOCK,
    get_airtable_sync_class,
)
from user.models import User


def create_guide(name):
    return ImplementationGuideBlueprint.objects.get_or_create(
        name=name, description='Guide description', updated_at=DATETIME_MOCK
    )


@pytest.fixture()
def guide_mock():
    return create_guide('Implementation Guide 001')


@pytest.fixture()
def guide_mock_2():
    return create_guide('Implementation Guide 002')


@pytest.fixture()
def implementation_guide_to_update_mock():
    ImplementationGuideBlueprint.objects.get_or_create(
        name='Test Guide 001',
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
                NAME: 'Asset Inventory',
                DESCRIPTION: 'Any description',
                LAST_MODIFIED: '2022-03-02T22:20:15.000Z',
            },
        },
        {
            'id': 'abcs5s5s',
            'fields': {
                NAME: 'External System Services',
                DESCRIPTION: 'My description',
                LAST_MODIFIED: '2022-03-01T22:20:15.000Z',
            },
        },
    ],
)
def test_airtable_sync_create_guides_blueprint(
    execute_airtable_request_mock, graphql_user: User
):
    expected_status_detail = [
        'Record created successfully: Asset Inventory',
        'Record created successfully: External System Services',
    ]

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    airtable_class_mock.update_blueprint(blueprint_base.update_or_create_object)

    execute_airtable_request_mock.assert_called_once()
    assert airtable_class_mock.status_detail == expected_status_detail
    assert ImplementationGuideBlueprint.objects.count() == 2
    assert ImplementationGuideBlueprint.objects.get(name='Asset Inventory')
    assert ImplementationGuideBlueprint.objects.get(name='External System Services')


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: 'New implementation guide',
                DESCRIPTION: 'Any description',
                LAST_MODIFIED: DATETIME_MOCK,
            },
        }
    ],
)
def test_airtable_init_update_guides_unit(
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
                NAME: 'Another implementation guide',
                DESCRIPTION: 'Any description',
                LAST_MODIFIED: '2022-07-02T22:22:26.000Z',
            },
        }
    ],
)
def test_airtable_sync_delete_guide_blueprint(
    execute_airtable_request_mock, graphql_user: User, guide_mock
):
    expected_status_detail = [
        'Record created successfully: Another implementation guide',
        "Records deleted: ['Implementation Guide 001']",
    ]

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    assert blueprint_base.init_update(airtable_class_mock)
    execute_airtable_request_mock.assert_called_once()

    assert airtable_class_mock.status_detail == expected_status_detail
    assert ImplementationGuideBlueprint.objects.count() == 1
    assert ImplementationGuideBlueprint.objects.get(name='Another implementation guide')


@pytest.mark.django_db
def test_airtable_sync_delete_guide_unit(graphql_user: User, guide_mock, guide_mock_2):
    guides_to_exclude = [
        {NAME: 'Implementation Guide 002', DESCRIPTION: 'Some desc'},
        {NAME: 'Implementation Guide 004', DESCRIPTION: 'Another desc'},
    ]

    blueprint_base = get_guide_blueprint_admin_mock()

    guides_deleted = blueprint_base.delete_objects(guides_to_exclude, graphql_user)
    assert len(guides_deleted) == 1
    assert guides_deleted[0] == 'Implementation Guide 001'


def get_guide_blueprint_admin_mock() -> BlueprintAdmin:
    return ImplementationGuideBlueprintAdmin(
        model=ImplementationGuideBlueprint, admin_site=AdminSite()
    )


def get_airtable_sync_class_mock(graphql_user: User) -> AirtableSync:
    return get_airtable_sync_class(graphql_user, GUIDES_REQUIRED_FIELDS)


def get_and_assert_base_mock_classes(
    graphql_user: User,
) -> Tuple[BlueprintAdmin, AirtableSync]:
    blueprint_base = get_guide_blueprint_admin_mock()
    assert blueprint_base

    airtable_class_mock = get_airtable_sync_class_mock(graphql_user)
    assert airtable_class_mock

    return blueprint_base, airtable_class_mock

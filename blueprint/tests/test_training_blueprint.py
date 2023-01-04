import os
from typing import Tuple
from unittest.mock import patch

import pytest
from django.contrib.admin import AdminSite
from django.core.files import File

from blueprint.admin import TrainingBlueprintAdmin
from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.commons import AirtableSync
from blueprint.constants import (
    CATEGORY,
    DESCRIPTION,
    FILE_ATTACHMENT,
    LAST_MODIFIED,
    NAME,
    TRAINING_REQUIRED_FIELDS,
)
from blueprint.models.training import TrainingBlueprint
from blueprint.tests.test_commons import (
    DATETIME_MOCK,
    RECORD_ID_MOCK,
    get_airtable_sync_class,
)
from user.models import User

FILE_NAME = 'Laika Security Awareness and Incident Response Training.pdf'
training_file_path = f'{os.path.dirname(__file__)}/resources/training.pdf'


def create_training(name, description, category):
    attachment_file = File(open(training_file_path, "rb"))
    return TrainingBlueprint.objects.get_or_create(
        name=name,
        description=description,
        category=category,
        file_attachment=File(name='training.pdf', file=attachment_file),
        updated_at=DATETIME_MOCK,
    )


def assert_training(
    execute_airtable_request_mock,
    test_class,
    expected_status_detail,
    expected_amount,
    expected_description,
):
    execute_airtable_request_mock.assert_called_once()
    assert test_class.status_detail == expected_status_detail
    assert TrainingBlueprint.objects.count() == expected_amount
    assert TrainingBlueprint.objects.get(description=expected_description)


@pytest.fixture()
def first_training_mock():
    return create_training('Training name', 'Training description', 'Compliance')


@pytest.fixture()
def second_training_mock():
    return create_training('Training name 2', 'Training description - 2', 'Compliance')


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: 'Training name',
                CATEGORY: 'Compliance',
                DESCRIPTION: 'Training description',
                FILE_ATTACHMENT: [
                    {
                        'id': 'att96aAQNh5t7j5nu',
                        'url': 'http://fakeurl.com/somelongfile',
                        'filename': FILE_NAME,
                        'size': 841852,
                        'type': 'application/pdf',
                        'thumbnails': {
                            'small': {
                                'url': 'http://fakeurl.com/somelongfile',
                                'width': 64,
                                'height': 36,
                            },
                            'large': {
                                'url': 'http://fakeurl.com/somelongfile',
                                'width': 512,
                                'height': 288,
                            },
                        },
                    }
                ],
                LAST_MODIFIED: '2022-03-01T23:19:58.000Z',
            },
        }
    ],
)
@patch('blueprint.helpers.get_attachment', return_value=FILE_NAME)
def test_airtable_sync_create_training_blueprint(
    get_attachment_mock, execute_airtable_request_mock, graphql_user
):
    expected_status_detail = ['Record created successfully: Training name']
    expected_amount_of_trainings = 1
    expected_description = 'Training description'

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    airtable_class_mock.update_blueprint(blueprint_base.update_or_create_object)

    assert_training(
        execute_airtable_request_mock,
        airtable_class_mock,
        expected_status_detail,
        expected_amount_of_trainings,
        expected_description,
    )


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: 'Training name',
                CATEGORY: 'Compliance',
                DESCRIPTION: 'Training description UPDATED',
                FILE_ATTACHMENT: [
                    {
                        'id': 'att96aAQNh5t7j5nu',
                        'url': 'http://fakeurl.com/somelongfile',
                        'filename': FILE_NAME,
                        'size': 841852,
                        'type': 'application/pdf',
                        'thumbnails': {
                            'small': {
                                'url': 'http://fakeurl.com/somelongfile',
                                'width': 64,
                                'height': 36,
                            },
                            'large': {
                                'url': 'http://fakeurl.com/somelongfile',
                                'width': 512,
                                'height': 288,
                            },
                        },
                    }
                ],
                LAST_MODIFIED: '2022-03-01T23:19:58.000Z',
            },
        }
    ],
)
@patch('blueprint.helpers.get_attachment', return_value=FILE_NAME)
def test_airtable_init_update_training(
    get_attachment_mock, execute_airtable_request_mock, graphql_user
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
                NAME: 'Training name - 3',
                CATEGORY: 'Compliance',
                DESCRIPTION: 'Training description - 3',
                FILE_ATTACHMENT: [
                    {
                        'id': 'att96aAQNh5t7j5nu',
                        'url': 'http://fakeurl.com/somelongfile',
                        'filename': FILE_NAME,
                        'size': 841852,
                        'type': 'application/pdf',
                        'thumbnails': {
                            'small': {
                                'url': 'http://fakeurl.com/somelongfile',
                                'width': 64,
                                'height': 36,
                            },
                            'large': {
                                'url': 'http://fakeurl.com/somelongfile',
                                'width': 512,
                                'height': 288,
                            },
                        },
                    }
                ],
                LAST_MODIFIED: '2022-03-01T23:19:58.000Z',
            },
        }
    ],
)
@patch('blueprint.helpers.get_attachment', return_value=FILE_NAME)
def test_airtable_sync_delete_training_blueprint(
    get_attachment_mock,
    execute_airtable_request_mock,
    graphql_user,
    first_training_mock,
):
    expected_status_detail = [
        'Record created successfully: Training name - 3',
        "Records deleted: ['Training name']",
    ]
    expected_amount_of_trainings = 1
    expected_description = 'Training description - 3'

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    assert blueprint_base.init_update(airtable_class_mock)

    assert_training(
        execute_airtable_request_mock,
        airtable_class_mock,
        expected_status_detail,
        expected_amount_of_trainings,
        expected_description,
    )


def get_and_assert_base_mock_classes(
    graphql_user: User,
) -> Tuple[BlueprintAdmin, AirtableSync]:
    blueprint_base = get_blueprint_admin_mock()
    assert blueprint_base

    airtable_class_mock = get_airtable_sync_class(
        graphql_user, TRAINING_REQUIRED_FIELDS
    )
    assert airtable_class_mock

    return blueprint_base, airtable_class_mock


def get_blueprint_admin_mock():
    return TrainingBlueprintAdmin(model=TrainingBlueprint, admin_site=AdminSite())

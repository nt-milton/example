from typing import Tuple
from unittest.mock import patch

import pytest
from django.contrib.admin import AdminSite

from blueprint.admin import QuestionBlueprintAdmin
from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.commons import AirtableSync
from blueprint.constants import (
    ANSWER,
    LAST_MODIFIED,
    QUESTION_TEXT,
    QUESTIONNAIRE,
    QUESTIONS_REQUIRED_FIELDS,
    SHORT_ANSWER,
    SHORT_ANSWER_OPTIONS,
)
from blueprint.models.question import QuestionBlueprint
from blueprint.tests.test_commons import (
    DATETIME_MOCK,
    RECORD_ID_MOCK,
    get_airtable_sync_class,
)
from user.models import User


def create_question(name):
    return QuestionBlueprint.objects.get_or_create(
        question_text=name,
        questionnaire='Kickstart',
        answer='Charter content for team',
        short_answer='Yes',
        short_answer_options=(
            '{"answer":{"address":"S!B1", "options":[]},'
            '"shortAnswer":{"address":"S!C1","options": []}}'
        ),
        updated_at=DATETIME_MOCK,
    )


def assert_teams(
    execute_airtable_request_mock,
    test_class,
    expected_status_detail,
    expected_amount,
    expected_name,
):
    execute_airtable_request_mock.assert_called_once()
    assert test_class.status_detail == expected_status_detail
    assert QuestionBlueprint.objects.count() == expected_amount
    assert QuestionBlueprint.objects.get(question_text=expected_name)


@pytest.fixture()
def question_mock():
    return create_question('Question 001')


@pytest.fixture()
def question_mock_2():
    return create_question('Question 002')


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                QUESTION_TEXT: 'Question 1',
                QUESTIONNAIRE: 'Kickstart',
                ANSWER: 'My long answer',
                SHORT_ANSWER: 'Yes',
                SHORT_ANSWER_OPTIONS: '{}',
                LAST_MODIFIED: '2022-03-02T22:20:15.000Z',
            },
        }
    ],
)
def test_airtable_sync_create_questions_blueprint(
    execute_airtable_request_mock, graphql_user
):
    expected_status_detail = ['Record created successfully: Question 1']
    expected_amount_of_questions = 1
    expected_question_name = 'Question 1'

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    airtable_class_mock.update_blueprint(blueprint_base.update_or_create_object)

    assert_teams(
        execute_airtable_request_mock,
        airtable_class_mock,
        expected_status_detail,
        expected_amount_of_questions,
        expected_question_name,
    )


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                QUESTION_TEXT: 'Question 1',
                QUESTIONNAIRE: 'Kickstart',
                ANSWER: 'My long answer',
                SHORT_ANSWER: 'Yes',
                LAST_MODIFIED: '2022-03-02T22:20:15.000Z',
            },
        }
    ],
)
def test_airtable_init_update_questions_unit(
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
                QUESTION_TEXT: 'Question 1',
                QUESTIONNAIRE: 'Kickstart',
                ANSWER: 'My long answer',
                SHORT_ANSWER: 'Yes',
                SHORT_ANSWER_OPTIONS: '{}',
                LAST_MODIFIED: '2022-03-01T23:19:58.000Z',
            },
        }
    ],
)
def test_airtable_sync_delete_question_blueprint(
    execute_airtable_request_mock, graphql_user, question_mock
):
    expected_status_detail = [
        'Record created successfully: Question 1',
        "Records deleted: ['Question 001']",
    ]
    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    expected_amount_of_teams = 1
    expected_team_name = 'Question 1'

    assert blueprint_base.init_update(airtable_class_mock)

    assert_teams(
        execute_airtable_request_mock,
        airtable_class_mock,
        expected_status_detail,
        expected_amount_of_teams,
        expected_team_name,
    )


@pytest.mark.django_db
def test_airtable_sync_delete_question_unit(
    graphql_user, question_mock, question_mock_2
):
    objects_to_exclude = [
        {QUESTION_TEXT: 'Question 002'},
        {QUESTION_TEXT: 'Question 004'},
    ]
    objects_deleted = get_blueprint_admin_mock().delete_objects(
        objects_to_exclude, graphql_user
    )
    assert len(objects_deleted) == 1
    assert objects_deleted == ['Question 001']


def get_and_assert_base_mock_classes(
    graphql_user: User,
) -> Tuple[BlueprintAdmin, AirtableSync]:
    blueprint_base = get_blueprint_admin_mock()
    assert blueprint_base

    airtable_class_mock = get_airtable_sync_class(
        graphql_user, QUESTIONS_REQUIRED_FIELDS
    )
    assert airtable_class_mock

    return blueprint_base, airtable_class_mock


def get_blueprint_admin_mock():
    return QuestionBlueprintAdmin(model=QuestionBlueprint, admin_site=AdminSite())

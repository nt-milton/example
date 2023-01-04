from typing import Tuple
from unittest.mock import patch

import pytest
from django.contrib.admin import AdminSite

from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.admin.team import TeamBlueprintAdmin
from blueprint.commons import AirtableSync
from blueprint.constants import (
    CHARTER,
    DESCRIPTION,
    LAST_MODIFIED,
    NAME,
    TEAMS_REQUIRED_FIELDS,
)
from blueprint.models.team import TeamBlueprint
from blueprint.tests.test_commons import (
    DATETIME_MOCK,
    RECORD_ID_MOCK,
    get_airtable_sync_class,
)
from user.models import User


def create_team(name):
    return TeamBlueprint.objects.get_or_create(
        name=name,
        description='Team description',
        charter='Charter content for team',
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
    assert TeamBlueprint.objects.count() == expected_amount
    assert TeamBlueprint.objects.get(name=expected_name)


@pytest.fixture()
def team_mock():
    return create_team('Team 001')


@pytest.fixture()
def team_mock_2():
    return create_team('Team 002')


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: 'Incident Response Team',
                DESCRIPTION: 'Any description',
                CHARTER: 'Any content',
                LAST_MODIFIED: '2022-03-02T22:20:15.000Z',
            },
        }
    ],
)
def test_airtable_sync_create_teams_blueprint(
    execute_airtable_request_mock, graphql_user
):
    expected_status_detail = ['Record created successfully: Incident Response Team']
    expected_amount_of_teams = 1
    expected_team_name = 'Incident Response Team'

    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    airtable_class_mock.update_blueprint(blueprint_base.update_or_create_object)

    assert_teams(
        execute_airtable_request_mock,
        airtable_class_mock,
        expected_status_detail,
        expected_amount_of_teams,
        expected_team_name,
    )


@pytest.mark.django_db
@patch(
    'blueprint.commons.execute_airtable_request',
    return_value=[
        {
            'id': RECORD_ID_MOCK,
            'fields': {
                NAME: 'Incident Response Team',
                DESCRIPTION: 'Any description',
                CHARTER: 'Any content',
                LAST_MODIFIED: '2022-03-02T22:20:15.000Z',
            },
        }
    ],
)
def test_airtable_init_update_teams_unit(execute_airtable_request_mock, graphql_user):
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
                NAME: 'New team',
                DESCRIPTION: 'Any description',
                CHARTER: 'Any content',
                LAST_MODIFIED: '2022-03-01T23:19:58.000Z',
            },
        }
    ],
)
def test_airtable_sync_delete_team_blueprint(
    execute_airtable_request_mock, graphql_user, team_mock
):
    expected_status_detail = [
        'Record created successfully: New team',
        "Records deleted: ['Team 001']",
    ]
    blueprint_base, airtable_class_mock = get_and_assert_base_mock_classes(graphql_user)

    expected_amount_of_teams = 1
    expected_team_name = 'New team'

    assert blueprint_base.init_update(airtable_class_mock)

    assert_teams(
        execute_airtable_request_mock,
        airtable_class_mock,
        expected_status_detail,
        expected_amount_of_teams,
        expected_team_name,
    )


@pytest.mark.django_db
def test_airtable_sync_delete_team_unit(graphql_user, team_mock, team_mock_2):
    objects_to_exclude = [{NAME: 'Team 002'}, {NAME: 'Team 004'}]
    objects_deleted = get_blueprint_admin_mock().delete_objects(
        objects_to_exclude, graphql_user
    )
    assert len(objects_deleted) == 1
    assert objects_deleted == ['Team 001']


def get_and_assert_base_mock_classes(
    graphql_user: User,
) -> Tuple[BlueprintAdmin, AirtableSync]:
    blueprint_base = get_blueprint_admin_mock()
    assert blueprint_base

    airtable_class_mock = get_airtable_sync_class(graphql_user, TEAMS_REQUIRED_FIELDS)
    assert airtable_class_mock

    return blueprint_base, airtable_class_mock


def get_blueprint_admin_mock():
    return TeamBlueprintAdmin(model=TeamBlueprint, admin_site=AdminSite())

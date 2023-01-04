import json
from unittest import mock

import pytest

from integration.jira.implementation import build_map_change_requests
from integration.store import Mapper, update_laika_objects
from integration.tests.factory import create_connection_account
from objects.models import LaikaObject
from objects.system_types import CHANGE_REQUEST


def get_jira_data():
    data = []
    with open('integration/tests/response_mocks/jira_response.mock.json') as f:
        data = json.load(f)
    return data


@pytest.fixture
def connection_account(graphql_organization):
    connection_account = create_connection_account(
        vendor_name='Vendor Test',
        alias='Connection 1',
        organization=graphql_organization,
    )
    connection_account.save = mock.Mock(return_value=None)
    return connection_account


@pytest.mark.functional
def test_create_laika_objects(connection_account):
    """Test update_laika_objects creates objects"""
    before_object_count = LaikaObject.objects.count()
    mapper = Mapper(
        map_function=build_map_change_requests(''),
        keys=['Key'],
        laika_object_spec=CHANGE_REQUEST,
    )
    data = get_jira_data()
    issues = data['issues']
    update_laika_objects(connection_account, mapper, issues)
    after_object_count = LaikaObject.objects.count()
    assert before_object_count == 0
    assert after_object_count == data['total']


@pytest.mark.functional
def test_create_laika_objects_with_mapper_error(connection_account):
    with pytest.raises(ValueError) as excinfo:
        mapper = Mapper(
            map_function=build_map_change_requests(''),
            keys=['Key'],
            laika_object_spec=CHANGE_REQUEST,
        )
        data = [{"dfsdf": "dsfsdfsdfsdad"}]
        update_laika_objects(connection_account, mapper, data)
    assert "Mapping error raw: {'dfsdf': 'dsfsdfsdfsdad'}" == str(excinfo.value)


@pytest.mark.functional
def test_updates_laika_objects_updates_object(connection_account):
    """Test update_laika_objects updates objects"""
    before_object_count = LaikaObject.objects.count()
    mapper = Mapper(
        map_function=build_map_change_requests(''),
        keys=['Key'],
        laika_object_spec=CHANGE_REQUEST,
    )
    data = get_jira_data()
    issues = data['issues']
    key = issues[0]['key']
    update_laika_objects(connection_account, mapper, issues)
    original_lo = LaikaObject.objects.get(**{'data__Key': key})
    original_title = issues[0]['fields']['summary']

    new_title = 'TESTing it updates'
    issues[0]['fields']['summary'] = new_title
    update_laika_objects(connection_account, mapper, issues)
    after_object_count = LaikaObject.objects.count()
    modified_lo = LaikaObject.objects.get(**{'data__Key': key})
    assert before_object_count == 0
    assert after_object_count == data['total']
    assert modified_lo.data['Title'] == new_title
    assert original_lo.data['Title'] == original_title


@pytest.mark.functional
def test_updates_laika_objects_deletes_object(connection_account):
    """Test update_laika_objects deletes objects"""
    before_object_count = LaikaObject.objects.count()
    mapper = Mapper(
        map_function=build_map_change_requests(''),
        keys=['Key'],
        laika_object_spec=CHANGE_REQUEST,
    )
    data = get_jira_data()
    issues = data['issues']
    update_laika_objects(connection_account, mapper, issues)

    new_issues = issues[:3]
    update_laika_objects(connection_account, mapper, new_issues)
    after_object_count = LaikaObject.objects.filter(deleted_at__isnull=True).count()
    assert before_object_count == 0
    assert after_object_count == len(new_issues)

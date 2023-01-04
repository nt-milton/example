import json
from datetime import datetime
from http import HTTPStatus
from unittest.mock import patch

import pytest
from dateutil.relativedelta import relativedelta

from integration.jira import rest_client
from integration.jira.rest_client import JIRA_ATTEMPTS
from laika.tests import mock_responses

ISSUES = [{'id': 'test_id'}]


@pytest.fixture
def failure():
    error_content = '{"message": "Unexpected response"}'
    return dict(status_code=HTTPStatus.NOT_FOUND, content=error_content)


@pytest.fixture
def success():
    content = f'{{"total":1, "issues":{json.dumps(ISSUES)} }}'
    return dict(status_code=HTTPStatus.OK, content=content)


def test_jira_retry_after_failure(failure, success):
    with mock_responses([failure, success]):
        has_next, tickets = rest_client.get_tickets_page('cloud_id', 'auth_token')

    assert has_next is False
    assert tickets == ISSUES


def test_jira_error_with_max_attempts(failure):
    with pytest.raises(ConnectionError) as excinfo:
        with mock_responses([failure for _ in range(JIRA_ATTEMPTS)]):
            rest_client.get_tickets_page('cloud_id', 'auth_token')

    assert 'Jira error' in str(excinfo.value)


def test_many_get_jql_projects():
    jql = rest_client._get_jql_projects(['TR', 'FZ'])
    assert jql == '("TR", "FZ")'


def test_one_get_jql_project():
    jql = rest_client._get_jql_projects(['TR'])
    assert jql == '("TR")'


def test_get_jql_projects_without_selections():
    jql = rest_client._get_jql_projects([])
    assert jql is None


def test_get_tickets_page_with_projects_filter():
    finish_date = datetime.now() - relativedelta(months=6)
    date_range = finish_date.strftime("%Y-%m-%d")
    cloud_id = 1
    page = 0
    max_results = 100
    jira_projects = ['TR', 'FZ']

    with patch('integration.jira.rest_client.get_resource_page') as mock_rest:
        search_url = 'https://api.atlassian.com/ex/jira/1/rest/api/2/search'
        jql = (
            'project in ("TR", "FZ") '
            f'AND createdDate >= "{date_range}" '
            'order by updated DESC'
        )
        pagination = f'maxResults={max_results}&startAt={0 * max_results}'
        url = f'{search_url}?expand=changelog&jql={jql}&{pagination}'
        rest_client.get_tickets_page(
            cloud_id=cloud_id,
            auth_token='MyToken',
            page=page,
            max_results=max_results,
            jira_projects=jira_projects,
            date_range_filter=date_range,
        )

        mock_rest.assert_called_once_with(url, page, max_results, 'issues', 'MyToken')

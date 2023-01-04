import json
from pathlib import Path
from unittest.mock import Mock, call

import pytest
from httmock import response as mock_response
from tenacity import wait_none

from integration.exceptions import ConfigurationError
from integration.github.http_client import (
    GITHUB_ATTEMPTS,
    _build_repo_query,
    _graphql_query,
    _iterate_github_page,
    flatten_github_org_response,
    flatten_github_user_response,
    flatten_pull_request_response,
    flatten_repository_response,
)
from laika.tests import mock_responses

END_PAGE_INFO = {'endCursor': 'Y3Vyc29yOnYyOpHODu-ArA==', 'hasNextPage': False}
TOKEN = '758f45b211e96f16441fbe6fdbab6d38ac9c7aef'
PARENT_PATH = Path(__file__).parent


@pytest.fixture
def github_orgs():
    path = PARENT_PATH / 'raw_org_response.json'
    return json.loads(open(path, 'r').read())


@pytest.fixture
def github_repositories():
    path = PARENT_PATH / 'raw_repo_response.json'
    return json.loads(open(path, 'r').read())


@pytest.fixture
def github_pull_requests():
    path = PARENT_PATH / 'raw_pr_response.json'
    return json.loads(open(path, 'r').read())


@pytest.fixture
def github_users():
    path = PARENT_PATH / 'raw_user_response.json'
    return json.loads(open(path, 'r').read())


def test_github_pagination():
    first_page_end_cursor = 'first_page_end_cursor'
    pages = [
        ({'endCursor': first_page_end_cursor, 'hasNextPage': True}, []),
        ({'endCursor': 'last_page_end_cursor', 'hasNextPage': False}, []),
    ]
    mock_http_call = Mock()
    mock_http_call.side_effect = pages

    fixed_arg = 'fixed_arg'
    list(_iterate_github_page(mock_http_call, fixed_arg=fixed_arg))
    assert mock_http_call.call_count == len(pages)
    mock_http_call.assert_has_calls(
        [
            call(end_cursor=None, fixed_arg=fixed_arg),
            call(end_cursor=first_page_end_cursor, fixed_arg=fixed_arg),
        ]
    )


def test_flatten_repositories_page_info(github_repositories):
    page_info, _ = flatten_repository_response(github_repositories)
    assert page_info == END_PAGE_INFO


def test_flatten_repositories_nodes(github_repositories):
    _, repositories = flatten_repository_response(github_repositories)
    repo_names = [r['name'] for r in repositories]
    assert repo_names == ['laika-web', 'laika-app']


def test_flatten_pull_requests_page_info(github_pull_requests):
    page_info, _ = flatten_pull_request_response(github_pull_requests)
    expected = END_PAGE_INFO
    assert page_info == expected


def test_flatten_pull_requests_nodes(github_pull_requests):
    _, pull_requests = flatten_pull_request_response(github_pull_requests)
    pr_numbers = [pr.get('number') for pr in pull_requests]
    assert pr_numbers == [1, 2, 3, 4, 5]


def test_flatten_github_org(github_orgs):
    page_info, github_org = flatten_github_org_response(github_orgs)
    assert page_info == END_PAGE_INFO
    assert github_org == [
        {'login_name': 'LaikaTest', 'profile_name': 'Laika Test 1'},
        {'login_name': 'LaikaTest-2', 'profile_name': 'Laika Test 2'},
    ]


def test_flatten_user_edges(github_users):
    _, users = flatten_github_user_response(github_users)
    admins = [True if user.get('role') == "ADMIN" else None for user in users]
    assert admins.count(True) == 12


def test_flatten_github_org_without_org():
    empty_response = '''
    {
      "data": {
        "viewer": {
          "organizations": {
            "pageInfo": {
              "endCursor": null,
              "hasNextPage": false
            },
            "nodes": []
          }
        }
      }
    }
    '''
    git_response = json.loads(empty_response)

    page_info, github_org = flatten_github_org_response(git_response)

    assert page_info == {'endCursor': None, 'hasNextPage': False}
    assert github_org == []


@pytest.fixture
def failure():
    content_error = '{"errors": [{"message":"Unexpected response"}]}'
    return mock_response(status_code=200, content=content_error)


@pytest.fixture
def success(github_pull_requests):
    content = json.dumps(github_pull_requests)
    return mock_response(status_code=200, content=content)


@pytest.fixture
def disable_wait_for_retry():
    _graphql_query.retry.wait = wait_none()


def test_github_retry_after_failure(
    disable_wait_for_retry, failure, success, github_pull_requests
):
    with mock_responses([failure, success]):
        response = _graphql_query('query', '')

    assert response == github_pull_requests


def test_github_error_with_max_attempts(disable_wait_for_retry, failure):
    with pytest.raises(ConfigurationError) as excinfo:
        with mock_responses([failure for _ in range(GITHUB_ATTEMPTS)]):
            _graphql_query('query', 'token')

    assert 'Provider GraphQL API error' in str(excinfo.value)


def test_build_repo_query_with_privacy():
    organization_name = 'heylaika'
    query = _build_repo_query(
        org=organization_name,
        end_cursor=None,
        visibility=['PRIVATE'],
    )
    repo_filter = 'first: 100, after: null, privacy: PRIVATE'
    assert (
        query
        == f'''
        query {{
          organization(login: "{organization_name}") {{
            repositories({repo_filter}) {{
              pageInfo {{
                endCursor
                hasNextPage
              }}
              nodes {{
                name
                description
                owner {{
                  name:login
                }}
                isDisabled
                isPrivate
                updatedAt
                createdAt
                url
              }}
            }}
          }}
        }}
    '''
    )


def test_build_repo_query_without_privacy():
    organization_name = 'heylaika'
    query = _build_repo_query(
        org=organization_name,
        end_cursor=None,
        visibility=None,
    )
    repo_filter = 'first: 100, after: null'
    assert (
        query
        == f'''
        query {{
          organization(login: "{organization_name}") {{
            repositories({repo_filter}) {{
              pageInfo {{
                endCursor
                hasNextPage
              }}
              nodes {{
                name
                description
                owner {{
                  name:login
                }}
                isDisabled
                isPrivate
                updatedAt
                createdAt
                url
              }}
            }}
          }}
        }}
    '''
    )

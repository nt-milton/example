import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from integration.github_apps import rest_client

PARENT_PATH = Path(__file__).parent


def get_prs(response):
    return response['data']['organization']['repository']['pullRequests']


@pytest.fixture
def github_pr_simple_response():
    path = PARENT_PATH / 'raw_pr_simple_response.json'
    return json.loads(open(path, 'r').read())


@pytest.fixture
def github_pr_full_response():
    path = PARENT_PATH / 'raw_pr_full_response.json'
    return json.loads(open(path, 'r').read())


@pytest.fixture
def github_pr_full_response_page_2():
    path = PARENT_PATH / 'raw_pr_full_response_page_2.json'
    return json.loads(open(path, 'r').read())


def test_build_pull_request_query_everything():
    repository = {'name': 'laika-app', 'owner': {'name': 'laika'}}
    query = rest_client._build_pull_request_query(
        repository=repository, end_cursor='Y3Vyc29yOjkwMA=='
    )
    order_by = 'orderBy: {field: UPDATED_AT, direction: DESC}'
    pr_filter = f'first: 100, after: "Y3Vyc29yOjkwMA==", {order_by}'
    assert (
        query
        == '''
        query {
          organization(login: "laika") {
            repository(name: "laika-app") {
              pullRequests({pr_filter}) {
                pageInfo {
                  endCursor
                  hasNextPage
                }
                nodes {
                  number
                  weblink:url
                  title
                  target:baseRefName
                  source:headRefName
                  state
                  reviewDecision
                  reviews(last: 3, states: [APPROVED,CHANGES_REQUESTED]) {
                      nodes {
                          state
                          author {
                              login
                          }
                      }
                  }
                  author {
                      login
                  }
                  createdAt
                  updatedAt
                }
              }
            }
          }
        }
    '''.replace(
            '{pr_filter}', pr_filter
        )
    )


@patch('integration.github_apps.rest_client._graphql_query')
def test_pull_request_page_ids_only(
    mock_github_gql: Mock,
    github_pr_simple_response,
):
    mock_github_gql.return_value = github_pr_simple_response
    repository = {'name': 'laika-app', 'owner': {'name': 'laika'}}
    response = rest_client._pull_request_page(lambda: 'token', repository, 'cursor')
    prs_keys = len(response[1][0])
    assert prs_keys == 2


@patch('integration.github_apps.rest_client._graphql_query')
def test_pull_request_page_everything(
    mock_github_gql: Mock,
    github_pr_full_response,
):
    mock_github_gql.return_value = github_pr_full_response
    repository = {'name': 'laika-app', 'owner': {'name': 'laika'}}
    response = rest_client._pull_request_page(lambda: 'token', repository, 'cursor')
    prs_keys = len(response[1][0])
    assert prs_keys == 11

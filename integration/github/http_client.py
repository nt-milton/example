import logging
import time
from datetime import datetime
from typing import Dict, Union

from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.exceptions import (
    ConfigurationError,
    GatewayTimeoutException,
    TimeoutException,
    TooManyRequests,
)
from integration.integration_utils.github_utils import (
    flatten_github_members_by_teams_response,
    flatten_github_org_response,
    flatten_github_user_response,
    flatten_pull_request_response,
    flatten_repository_response,
    get_graphql_query_headers,
)
from integration.log_utils import log_action, log_request
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import (
    GITHUB_API_URL,
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    GITHUB_OAUTH_URL,
)

GITHUB_PAGE_SIZE = 100
NUMBER_OF_REVIEWERS = 3
GITHUB_ATTEMPTS = 3
API_LIMIT = 1


logger_name = __name__
logger = logging.getLogger(logger_name)

retry_condition = (
    retry_if_exception_type(ConnectionError)
    | retry_if_exception_type(TooManyRequests)
    | retry_if_exception_type(ConfigurationError)
    | retry_if_exception_type(TimeoutException)
    | retry_if_exception_type(GatewayTimeoutException)
)


def _log_values(is_generator: bool = False):
    return dict(
        vendor_name='Github', logger_name=logger_name, is_generator=is_generator
    )


@retry(
    stop=stop_after_attempt(GITHUB_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def create_refresh_token(code: str, redirect_uri: str, **kwargs):
    data = {
        'grant_type': 'authorization_code',
        'client_secret': GITHUB_CLIENT_SECRET,
        'client_id': GITHUB_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'code': code,
    }
    headers = {
        'content-type': 'application/x-www-form-urlencoded',
        'accept': 'application/json',
    }
    url = GITHUB_OAUTH_URL
    log_request(url, 'create_refresh_token', logger_name, **kwargs)
    response = requests.post(
        GITHUB_OAUTH_URL, data=data, headers=headers, timeout=REQUESTS_TIMEOUT
    )
    wait_if_api_limit(response)
    raise_client_exceptions(response=response, **kwargs)

    return response.json()


def read_all_github_organizations(token: str, **kwargs):
    merged_kwargs = {**dict(token=token), **kwargs}
    return _iterate_github_page(_organization_page, **merged_kwargs)


def read_all_pull_requests(
    org: str, repo_visibility: str, token: str, selected_time_range: str, **kwargs
):
    repo_kwargs = {**dict(org=org, token=token, visibility=repo_visibility), **kwargs}
    repositories = _iterate_github_page(_repo_page, **repo_kwargs)
    for repo in repositories:
        org = repo['owner']['name']
        repo_name = repo['name']
        pr_visibility = 'Private' if repo['isPrivate'] else 'Public'
        pr_kwargs = {**dict(org=org, repo=repo_name, token=token), **kwargs}
        pull_requests = _iterate_github_page(_pull_request_page, **pr_kwargs)
        filtered_pull_requests = _pull_request_date_filter(
            pull_requests, selected_time_range
        )
        for pr in filtered_pull_requests:
            yield repo_name, pr, pr_visibility


def read_all_repositories(github_org, repo_visibility, token, **kwargs):
    all_repo_kwargs = {
        **dict(org=github_org, token=token, visibility=repo_visibility),
        **kwargs,
    }
    repos = [repo for repo in _iterate_github_page(_repo_page, **all_repo_kwargs)]
    return repos


def read_all_organization_users(github_organization: str, access_token: str, **kwargs):
    users_kwargs = {**dict(org=github_organization, token=access_token), **kwargs}
    users = _iterate_github_page(_user_page, **users_kwargs)
    for user in users:
        yield user


def read_all_organization_members_by_teams(
    github_organization: Dict, access_token: str, **kwargs
):
    teams_kwargs = {
        **dict(github_organization=github_organization, token=access_token),
        **kwargs,
    }
    members_by_teams = _iterate_github_page(_get_members_by_teams, **teams_kwargs)
    for members_by_team in members_by_teams:
        yield members_by_team


def _iterate_github_page(call, **kwargs):
    """It returns a stream of nodes across pages, so callers do not need
    to deal GitHub pages"""
    end_cursor = None
    has_next_page = True
    while has_next_page:
        page_info, nodes = call(end_cursor=end_cursor, **kwargs)
        end_cursor = page_info.get('endCursor', None)
        has_next_page = page_info.get('hasNextPage', False)
        for node in nodes:
            yield node


@log_action(**_log_values())
def _organization_page(token: str, end_cursor=None, **kwargs):
    query = _build_organization_query(end_cursor)
    response = _graphql_query(query, token, **kwargs)
    return flatten_github_org_response(response)


@log_action(**_log_values())
def _repo_page(org: str, token: str, visibility=None, end_cursor=None, **kwargs):
    query = _build_repo_query(org, end_cursor, visibility)
    response = _graphql_query(query, token, **kwargs)
    return flatten_repository_response(response)


@log_action(**_log_values())
def _pull_request_page(org: str, repo: str, token: str, end_cursor=None, **kwargs):
    query = _build_pull_request_query(org, repo, end_cursor)
    response = _graphql_query(query, token, **kwargs)
    return flatten_pull_request_response(response)


@log_action(**_log_values())
def _user_page(token, org, end_cursor=None, **kwargs):
    query = _build_users_query(org, end_cursor)
    response = _graphql_query(query, token, **kwargs)
    return flatten_github_user_response(response)


@log_action(**_log_values())
def _get_members_by_teams(
    token: str, github_organization: str, end_cursor: Union[str, None] = None, **kwargs
):
    query = _build_members_by_teams_query(
        github_organization=github_organization, end_cursor=end_cursor
    )
    response = _graphql_query(query=query, token=token, **kwargs)
    return flatten_github_members_by_teams_response(response=response)


@retry(
    stop=stop_after_attempt(GITHUB_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
def _graphql_query(query: str, token: str, **kwargs):
    url = GITHUB_API_URL
    log_request(url, '_graphql_query', logger_name, **kwargs)
    response = requests.post(
        url,
        json={'query': query},
        headers=get_graphql_query_headers(token),
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_api_limit(response)
    raise_client_exceptions(response=response, is_graph_api=True, **kwargs)
    return response.json()


def _build_organization_query(end_cursor):
    org_filter = _page_filter(end_cursor)
    return f'''
        query {{
          viewer {{
            organizations({org_filter}) {{
              pageInfo {{
                endCursor
                hasNextPage
              }}
              nodes {{
                login_name:login
                profile_name:name
              }}
            }}
          }}
        }}
    '''


def _build_repo_query(org, end_cursor, visibility=None):
    repo_filter = _page_filter(end_cursor)
    if visibility and len(visibility) == 1:
        repo_filter = f'{repo_filter}, privacy: {visibility[0]}'
    return f'''
        query {{
          organization(login: "{org}") {{
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


def _build_pull_request_query(org, repo, end_cursor):
    pr_filter = _page_filter(end_cursor)
    order_by = 'orderBy: {field: CREATED_AT, direction: DESC}'
    return f'''
        query {{
          organization(login: "{org}") {{
            repository(name: "{repo}") {{
              pullRequests({pr_filter}, {order_by}) {{
                pageInfo {{
                    endCursor
                    hasNextPage
                }}
                nodes {{
                    number
                    weblink:url
                    title
                    target:baseRefName
                    source:headRefName
                    state
                    reviewDecision
                    reviews(last:{NUMBER_OF_REVIEWERS}, states: [APPROVED]) {{
                      nodes {{
                        state
                        author{{
                          login
                        }}
                      }}
                    }}
                    author {{
                      login
                    }}
                    createdAt
                    updatedAt
                  }}
              }}
            }}
          }}
        }}
    '''


def _build_users_query(org, end_cursor):
    user_filter = _page_filter(end_cursor)
    return f'''
        query {{
          organization(login: "{org}") {{
            membersWithRole({user_filter}) {{
              pageInfo {{
                endCursor
                hasNextPage
              }}
              edges {{
                hasTwoFactorEnabled
                role
                node {{
                  id
                  name
                  email
                  login
                  organization(login: "{org}") {{
                    name
                  }}
                }}
              }}
            }}
          }}
        }}
    '''


def _build_members_by_teams_query(
    github_organization: str, end_cursor: Union[str, None]
):
    teams_filter = _page_filter(end_cursor)
    return f'''
        query {{
          organization(login: "{github_organization}") {{
            teams({teams_filter}) {{
              pageInfo {{
                endCursor
                hasNextPage
              }}
              nodes {{
                name
                members {{
                  nodes {{
                    login
                  }}
                }}
              }}
            }}
          }}
        }}
    '''


def _page_filter(end_cursor):
    after_filter = f'"{end_cursor}"' if end_cursor else 'null'
    return f'first: {GITHUB_PAGE_SIZE}, after: {after_filter}'


def _pull_request_date_filter(pull_requests, selected_time_range):
    filtered_pull_requests = []
    for pr in pull_requests:
        if pr['createdAt'] >= selected_time_range:
            filtered_pull_requests.append(pr)
            continue
        break
    return filtered_pull_requests


def wait_if_api_limit(response):
    requests_remaining = int(response.headers.get('X-RateLimit-Remaining', 1))
    reset_timestamp = int(response.headers.get('X-RateLimit-Reset', 0)) + 15
    if requests_remaining == API_LIMIT:
        current_timestamp = int(datetime.now().timestamp())
        wait_time = reset_timestamp - current_timestamp
        if wait_time >= 0:
            time.sleep(wait_time)

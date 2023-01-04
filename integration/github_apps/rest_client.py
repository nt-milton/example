import logging
import re
from typing import Callable, Dict, List, NamedTuple, TypedDict, Union

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.exceptions import TooManyRequests
from integration.github_apps.utils import (
    GITHUB_APPS_ATTEMPTS,
    GITHUB_PAGE_SIZE,
    SECONDARY_RATE_LIMIT_REGEX,
    get_jwt_token,
    get_pull_request_dict,
    get_pull_request_record,
)
from integration.integration_utils.constants import retry_condition
from integration.integration_utils.github_utils import (
    flatten_github_members_by_teams_response,
    flatten_github_user_response,
    flatten_pull_request_response,
    flatten_repository_response,
    get_graphql_query_headers,
)
from integration.log_utils import log_action, log_request, logger_extra
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import GITHUB_API_URL, GITHUB_APPS_URL
from integration.utils import wait_if_rate_time_api

logger_name = __name__
logger = logging.getLogger(logger_name)


def _log_values(is_generator: bool = False):
    return dict(
        vendor_name='Github Apps', logger_name=logger_name, is_generator=is_generator
    )


TokenProvider = Callable[[], str]


class GithubOrganization(NamedTuple):
    organization: str
    fetch_token: TokenProvider


@retry(
    stop=stop_after_attempt(GITHUB_APPS_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_organization(new_application: str, jwt_token: str):
    headers = {'Authorization': f'Bearer {jwt_token}'}
    url = f'{GITHUB_APPS_URL}/orgs/{new_application}/installation'
    log_request(url, 'get_app_installations', logger_name)
    response = requests.get(url=url, headers=headers, timeout=REQUESTS_TIMEOUT)
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)

    return response.json()


@retry(
    stop=stop_after_attempt(GITHUB_APPS_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_user(new_application: str, jwt_token: str):
    headers = {'Authorization': f'Bearer {jwt_token}'}
    url = f'{GITHUB_APPS_URL}/users/{new_application}/installation'
    log_request(url, 'get_user', logger_name)
    response = requests.get(url=url, headers=headers, timeout=REQUESTS_TIMEOUT)
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)

    return response.json()


@retry(
    stop=stop_after_attempt(GITHUB_APPS_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_installation_access_token(installation_id: str):
    jwt_token = get_jwt_token()
    headers = {'Authorization': f'Bearer {jwt_token}'}
    url = f'{GITHUB_APPS_URL}/app/installations/{installation_id}/access_tokens'
    log_request(url, 'get_installation_access_token', logger_name)
    response = requests.post(
        url=url, data={}, headers=headers, timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)

    return response.json()


def read_all_repositories(installed_app: GithubOrganization):
    repos = [
        repo
        for repo in _iterate_github_page(
            _repo_page,
            github_organization=installed_app.organization,
            token=installed_app.fetch_token(),
        )
    ]
    return repos


def read_all_organization_users(
    github_organization: str,
    token: TokenProvider,
):
    users = _iterate_github_page(
        _user_page, github_organization=github_organization, token=token
    )
    for user in users:
        yield user


def read_all_organization_members_by_teams(
    github_organization: str,
    access_token: TokenProvider,
):
    members_by_teams = _iterate_github_page(
        _get_members_by_teams,
        github_organization=github_organization,
        token=access_token,
    )
    for members_by_team in members_by_teams:
        yield members_by_team


def get_repository_pull_requests_and_next_page(
    installed_app: GithubOrganization,
    repository: Dict,
    has_next_page: bool = True,
    end_cursor: Union[str, None] = None,
    **kwargs,
):
    pull_requests_chunk: List = []
    chunks_limit = int(kwargs.get('chunks_limit', 1000))

    def _can_continue_fetching() -> bool:
        return has_next_page and len(pull_requests_chunk) < chunks_limit

    while _can_continue_fetching():
        page_info, pull_requests = _pull_request_page(
            access_token=installed_app.fetch_token,
            repository=repository,
            end_cursor=end_cursor,
        )
        end_cursor = page_info.get('endCursor')
        has_next_page = page_info.get('hasNextPage', False)

        for pull_request in pull_requests:
            repo_visibility = 'Private' if repository['isPrivate'] else 'Public'
            pull_request_record = get_pull_request_record(
                organization=installed_app.organization,
                repository=repository['name'],
                pr=get_pull_request_dict(pull_request),
                pr_visibility=repo_visibility,
            )
            pull_requests_chunk.append(pull_request_record)

    pagination_values: PaginationPullRequests = {
        'hast_next_page': has_next_page,
        'end_cursor': end_cursor,
    }

    return pull_requests_chunk, pagination_values


class PaginationPullRequests(TypedDict):
    hast_next_page: bool
    end_cursor: Union[str, None]


def _iterate_github_page(call, **kwargs):
    """It returns a stream of nodes across pages, so callers do not need
    to deal GitHub pages"""
    end_cursor = None
    has_next_page = True
    while has_next_page:
        data = call(end_cursor=end_cursor, **kwargs)
        page_info, nodes = data
        end_cursor = page_info.get('endCursor', None)
        has_next_page = page_info.get('hasNextPage', False)
        for node in nodes:
            yield node


@log_action(**_log_values())
def _repo_page(
    github_organization: str,
    token: str,
    visibility: str = None,
    end_cursor: str = None,
    **kwargs,
):
    query = _build_repo_query(github_organization, end_cursor, visibility)
    response = _graphql_query(query, token, **kwargs)
    # TODO: Remove in AB-1333 implementation
    if not response.get('data', {}).get('organization'):
        return {}, []
    return flatten_repository_response(response)


@log_action(**_log_values())
def _pull_request_page(
    access_token: TokenProvider,
    repository: Dict,
    end_cursor: Union[str, None] = None,
):
    query = _build_pull_request_query(repository, end_cursor)
    repo_name = repository.get('name')
    logger.info(logger_extra(f"PR's for repo {repo_name} - end cursor {end_cursor}"))
    response = _graphql_query(query, access_token())
    return flatten_pull_request_response(response)


@log_action(**_log_values())
def _user_page(
    token: TokenProvider,
    github_organization: str,
    end_cursor: Union[str, None] = None,
):
    query = _build_users_query(
        github_organization=github_organization, end_cursor=end_cursor
    )
    response = _graphql_query(query=query, token=token())
    # TODO: Remove in AB-1333 implementation
    if not response.get('data', {}).get('organization'):
        return {}, []
    return flatten_github_user_response(response=response)


@log_action(**_log_values())
def _get_members_by_teams(
    token: TokenProvider,
    github_organization: str,
    end_cursor: Union[str, None] = None,
):
    query = _build_members_by_teams_query(
        github_organization=github_organization, end_cursor=end_cursor
    )
    response = _graphql_query(query=query, token=token())
    # TODO: Remove in AB-1333 implementation
    if not response.get('data', {}).get('organization'):
        return {}, []
    return flatten_github_members_by_teams_response(response=response)


@retry(
    stop=stop_after_attempt(GITHUB_APPS_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
def _graphql_query(query: str, token: str):
    log_request(GITHUB_API_URL, 'graphql_query', logger_name)
    response = requests.post(
        url=GITHUB_API_URL,
        json={'query': query},
        headers=get_graphql_query_headers(token),
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response)
    result = raise_client_exceptions(
        response=response,
        is_graph_api=True,
        raise_exception=False,
    )
    if result.with_error():
        error_response = str(result.error_response)
        if re.search(SECONDARY_RATE_LIMIT_REGEX, error_response, re.IGNORECASE):
            logger.info(logger_extra(error_response))
            raise TooManyRequests(error_response)

        raise result.get_connection_result()

    return response.json()


def _build_repo_query(
    github_organization: str, end_cursor: Union[str, None], visibility: str = None
):
    repo_filter = _page_filter(end_cursor)
    if visibility and len(visibility) == 1:
        repo_filter = f'{repo_filter}, privacy: {visibility[0]}'
    return f'''
        query {{
          organization(login: "{github_organization}") {{
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


def _build_pull_request_query(repository: Dict, end_cursor: Union[str, None]):
    organization = repository['owner'].get('name')
    repository_name = repository.get('name')
    pr_filter = _page_filter(end_cursor)
    order_by = 'orderBy: {field: UPDATED_AT, direction: DESC}'

    return f'''
        query {{
          organization(login: "{organization}") {{
            repository(name: "{repository_name}") {{
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
                  reviews(last: 3, states: [APPROVED,CHANGES_REQUESTED]) {{
                      nodes {{
                          state
                          author {{
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


def _build_users_query(github_organization: str, end_cursor: Union[str, None]):
    user_filter = _page_filter(end_cursor)
    return f'''
        query {{
          organization(login: "{github_organization}") {{
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
                  organization(login: "{github_organization}") {{
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


def _page_filter(end_cursor: Union[str, None]) -> str:
    after_filter = f'"{end_cursor}"' if end_cursor else 'null'
    return f'first: {GITHUB_PAGE_SIZE}, after: {after_filter}'

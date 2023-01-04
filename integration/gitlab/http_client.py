import logging
from typing import Dict, List, NamedTuple

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT, SELF_MANAGED_SUBSCRIPTION
from integration.integration_utils.constants import retry_condition
from integration.log_utils import log_action, log_request
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import GITLAB_CLIENT_ID, GITLAB_CLIENT_SECRET
from integration.utils import wait_if_rate_time_api

logger_name = __name__
logger = logging.getLogger(logger_name)
GITLAB_PAGE_SIZE = 100
GITLAB_ATTEMPTS = 3


class AccessTokenRequest(NamedTuple):
    oauth_url: str
    client_id: str
    client_secret: str
    redirect_uri: str


def _log_values(is_generator: bool = False):
    return dict(
        vendor_name='Gitlab', logger_name=logger_name, is_generator=is_generator
    )


@log_action(**_log_values())
def create_access_token(
    refresh_token: str, access_token_request: AccessTokenRequest, **kwargs
):
    data = {
        'grant_type': 'refresh_token',
        'client_secret': access_token_request.client_secret,
        'client_id': access_token_request.client_id,
        'refresh_token': refresh_token,
        'redirect_uri': access_token_request.redirect_uri,
    }
    url = access_token_request.oauth_url
    headers = {'content-type': 'application/json'}
    log_request(url, 'create_access_token', logger_name, **kwargs)
    response = requests.post(
        url=url, json=data, headers=headers, timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, **kwargs)
    access_token = response.json().get('access_token')
    rotating_refresh_token = response.json().get('refresh_token', refresh_token)
    return access_token, rotating_refresh_token


@retry(
    stop=stop_after_attempt(GITLAB_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def create_refresh_token(code: str, redirect_uri: str, **kwargs):
    credentials = kwargs.get('credentials')
    app_credentials = _get_app_credentials(credentials)
    data = {
        'grant_type': 'authorization_code',
        'client_secret': app_credentials.get('client_secret'),
        'client_id': app_credentials.get('client_id'),
        'redirect_uri': redirect_uri,
        'code': code,
    }
    headers = {
        'content-type': 'application/x-www-form-urlencoded',
    }
    url = f"{app_credentials.get('base_url')}/oauth/token"
    log_request(url, 'create_refresh_token', logger_name, **kwargs)
    response = requests.post(
        url=url, data=data, headers=headers, timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, **kwargs)
    return response.json()


def _get_app_credentials(credentials) -> Dict[str, str]:
    is_self_hosted = credentials.get('subscriptionType')
    app_values = credentials.get('credentials')
    return (
        {
            'client_secret': app_values.get('secretId'),
            'client_id': app_values.get('clientId'),
            'base_url': app_values.get('baseUrl'),
        }
        if is_self_hosted == SELF_MANAGED_SUBSCRIPTION
        else {
            'client_secret': GITLAB_CLIENT_SECRET,
            'client_id': GITLAB_CLIENT_ID,
            'base_url': 'https://gitlab.com',
        }
    )


@retry(
    stop=stop_after_attempt(GITLAB_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def _graphql_query(query: str, access_token: str, **kwargs):
    credentials = kwargs.get('credentials')
    app_credentials = _get_app_credentials(credentials)
    headers = {
        'content-type': 'application/json; ',
        'accept': 'application/json',
        'Authorization': f'Bearer {access_token}',
    }
    url = f"{app_credentials.get('base_url')}/api/graphql"
    log_request(url, '_graphql_query', logger_name, **kwargs)
    response = requests.post(
        url=url, json={'query': query}, headers=headers, timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, is_graph_api=True, **kwargs)
    return response.json()


def _iterate_gitlab_page(call, **kwargs):
    """It returns a stream of nodes across pages, so callers do not need
    to deal GitHub pages"""
    end_cursor = None
    has_next_page = True
    while has_next_page:
        try:
            page_info, nodes = call(end_cursor=end_cursor, **kwargs)
            end_cursor = page_info.get('endCursor', None)
            has_next_page = page_info.get('hasNextPage', False)
            for node in nodes:
                yield node
        except Exception:
            break


def read_all_gitlab_groups(access_token: str, **kwargs):
    merged_kwargs = {**dict(access_token=access_token), **kwargs}
    groups = _iterate_gitlab_page(_groups_page, **merged_kwargs)
    return [group['group'] for group in groups]


def read_merge_request_gitlab(
    access_token, group_name, selected_time_range, visibility=None, **kwargs
):
    projects = _iterate_gitlab_page(
        _projects_page, group_name=group_name, access_token=access_token, **kwargs
    )
    projects_by_visibility = _projects_filtered(projects, visibility)
    for project in projects_by_visibility:
        project_visibility = project['visibility'].capitalize()
        project_id = project['id']
        merge_requests = _iterate_gitlab_page(
            _merge_request_page,
            group_name=group_name,
            project_id=project_id,
            access_token=access_token,
            **kwargs,
        )
        merge_requests_filtered_by_date = _merge_requests_filtered(
            merge_requests, selected_time_range
        )
        for mr in merge_requests_filtered_by_date:
            yield group_name, mr, project_visibility


def read_users_group(access_token, group_name, **kwargs):
    users = _iterate_gitlab_page(
        _user_group_page, access_token=access_token, group_name=group_name, **kwargs
    )
    user_admin_ids = _admin_users(access_token, **kwargs)
    for user in users:
        if user['user'] is not None:
            for user_admin_id in user_admin_ids:
                if user['user']['id'] == user_admin_id['id']:
                    user['user']['isAdmin'] = True
            yield user


def read_projects_gitlab(access_token, group_name, visibility, **kwargs):
    projects = _iterate_gitlab_page(
        _projects_page, group_name=group_name, access_token=access_token, **kwargs
    )
    filtered_projects = _projects_filtered(projects, visibility)
    for project in filtered_projects:
        yield group_name, project


@log_action(**_log_values())
def _groups_page(access_token, end_cursor=None, **kwargs):
    query = _build_query_groups(end_cursor)
    response = _graphql_query(query, access_token, **kwargs)
    return _flatten_all_gitlab_groups(response)


@log_action(**_log_values())
def _merge_request_page(
    group_name: str, project_id: str, access_token: str, end_cursor: str, **kwargs
):
    query = _build_query_merge_request(group_name, project_id, end_cursor)
    response = _graphql_query(query, access_token, **kwargs)
    return _flatten_all_gitlab_merge_request(response=response)


@log_action(**_log_values())
def _user_group_page(group_name, access_token, end_cursor, **kwargs):
    query = _build_query_group_users(group_name, end_cursor)
    response = _graphql_query(query, access_token, **kwargs)
    return _flatten_all_gitlab_user_per_group(response)


@log_action(**_log_values())
def _admin_users(access_token, **kwargs) -> List[Dict]:
    credentials = kwargs.get('credentials', {})
    if credentials.get('subscriptionType') == SELF_MANAGED_SUBSCRIPTION:
        response = _graphql_query(_build_get_admin_users(), access_token, **kwargs)
        return _flatten_all_gitlab_admin_users_ids(response)

    return []


@log_action(**_log_values())
def _projects_page(group_name, access_token, end_cursor, **kwargs):
    query = _build_query_group_projects(group_name, end_cursor)
    response = _graphql_query(query, access_token, **kwargs)
    return _flatten_all_gitlab_projects(response)


def _flatten_all_gitlab_user_per_group(response):
    users = response['data']['group']['groupMembers']
    return users['pageInfo'], users['nodes']


def _flatten_all_gitlab_admin_users_ids(response):
    return response['data']['users']['nodes']


def _flatten_all_gitlab_merge_request(response: Dict):
    projects = response['data']['group']['projects']
    merge_requests = projects['nodes'][0]['mergeRequests']
    return merge_requests['pageInfo'], merge_requests['nodes']


def _flatten_all_gitlab_groups(response):
    groups = response['data']['currentUser']['groupMemberships']
    return groups['pageInfo'], groups['nodes']


def _flatten_all_gitlab_projects(response):
    if response['data']['group']:
        groups = response['data']['group']['projects']
        return groups['pageInfo'], groups['nodes']
    logger.warning(f'Group not available in organization {response}')
    return None


def _build_query_groups(end_cursor):
    _group_filter = _page_filter(end_cursor)
    return f'''query {{
      currentUser{{
        groupMemberships({_group_filter}){{
          pageInfo{{
            endCursor
            hasNextPage
          }}
          nodes{{
            group{{
            fullPath
            fullName
            }}
          }}
        }}
      }}
    }}'''


def _build_query_merge_request(group_name: str, project_id: str, end_cursor: str):
    _merge_request_filter = _page_filter(end_cursor)
    return f'''query{{
      group(fullPath: "{group_name}") {{
        projects(ids:["{project_id}"]){{
         nodes{{
          mergeRequests({_merge_request_filter}, sort:CREATED_DESC) {{
          pageInfo {{
            endCursor
            hasNextPage
          }}
          nodes {{
            iid
            state
            approved
            title
            webUrl
            targetBranch
            sourceBranch
            approvalsRequired
            approvalsLeft
            author {{
              name
              username
            }}
            approvedBy {{
              nodes {{
                name
                username
              }}
            }}
            updatedAt
            createdAt
            project {{
              name
            }}
          }}
        }}
       }}
      }}
     }}
    }}'''


def _build_query_group_users(group_name, end_cursor):
    _user_filter = _page_filter(end_cursor)
    return f'''{{
     group(fullPath: "{group_name}") {{
        groupMembers({_user_filter}) {{
          pageInfo {{
            endCursor
            hasNextPage
          }}
          nodes {{
            user {{
              groupMemberships {{
                nodes {{
                  accessLevel{{
                    stringValue
                  }}
                  group {{
                    name
                    requireTwoFactorAuthentication
                  }}
                }}
              }}
              id
              name
              publicEmail
            }}
          }}
        }}
      }}
}}
'''


def _build_query_group_projects(group_name, end_cursor):
    _repo_filter = _page_filter(end_cursor)
    return f'''{{
     group(fullPath: "{group_name}") {{
        projects ({_repo_filter}) {{
          pageInfo {{
            endCursor
            hasNextPage
          }}
          nodes {{
            id
            name
            webUrl
            archived
            visibility
            lastActivityAt
            createdAt
          }}
        }}
      }}
}}
'''


def _build_get_admin_users():
    return '''
    {
      users(admins:true){
        nodes{
          id
        }
      }
    }
'''


def _page_filter(end_cursor):
    after_filter = f'"{end_cursor}"' if end_cursor else 'null'
    return f'first: {GITLAB_PAGE_SIZE}, after: {after_filter}'


def _projects_filtered(projects, visibility):
    filtered_projects = []
    for project in projects:
        if project['visibility'].upper() in visibility:
            filtered_projects.append(project)

    return filtered_projects


def _merge_requests_filtered(merge_requests, selected_time_range):
    filtered_merge_requests = []
    for mr in merge_requests:
        if mr['createdAt'] >= selected_time_range:
            filtered_merge_requests.append(mr)
            continue
        break
    return filtered_merge_requests

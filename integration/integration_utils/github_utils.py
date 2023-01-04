import logging

logger = logging.getLogger(__name__)


def flatten_repository_response(response):
    if not response.get('data', {}).get('organization'):
        logger.error(f'Unexpected response: {response}')
    organization = response['data']['organization']
    repositories = organization.get('repositories', {})
    return repositories['pageInfo'], repositories['nodes']


def flatten_pull_request_response(response):
    repository = response['data']['organization']['repository']
    pull_requests = repository.get('pullRequests', {})
    return pull_requests['pageInfo'], pull_requests['nodes']


def flatten_github_org_response(response):
    organizations = response['data']['viewer']['organizations']
    return organizations['pageInfo'], organizations['nodes']


def flatten_github_user_response(response):
    organization = response['data']['organization']
    users = organization.get('membersWithRole', {})
    return users['pageInfo'], users['edges']


def flatten_github_members_by_teams_response(response):
    organization = response['data']['organization']
    teams = organization.get('teams', {})
    return teams['pageInfo'], teams['nodes']


def get_graphql_query_headers(token: str) -> dict[str, str]:
    return {
        'content-type': 'application/json; ',
        'accept': 'application/json',
        'Authorization': f'Bearer {token}',
    }

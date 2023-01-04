from typing import Dict, List, Literal, NamedTuple, Optional, TypedDict

from objects.system_types import PullRequest, Repository, User

GITHUB_SYSTEM = 'GitHub Apps'


def get_pull_request_key(repository: str, pull_request_number: str) -> str:
    return f"{repository}-{pull_request_number}"


class RepositoryOwnerDict(TypedDict):
    name: str


class RepositoryDict(TypedDict):
    name: str
    description: str
    owner: RepositoryOwnerDict
    isDisabled: bool
    isPrivate: bool
    updatedAt: str
    createdAt: str
    url: str


class RepositoryRecord(NamedTuple):
    organization: str
    repository: RepositoryDict


class PullRequestDict(TypedDict, total=False):
    number: int
    updatedAt: str
    weblink: str
    title: str
    target: str
    source: str
    state: str
    reviewDecision: Optional[str]
    reviews: dict
    createdAt: str
    author: dict


class PullRequestRecord(NamedTuple):
    organization: str
    repository: str
    pr: PullRequestDict
    pr_visibility: Literal['Private', 'Public']


class TeamMembers(NamedTuple):
    team: str
    members: List


class GithubUser(TypedDict, total=False):
    id: str
    name: str
    email: str
    role: str
    title: str
    has_2fa: bool
    teams: List
    organization_name: str


def map_pull_requests_to_laika_object(pull_request_record, connection_name):
    data = pull_request_record.pr
    reviews = data.get('reviews', {})
    approvers = {
        review['author']['login']
        for review in reviews['nodes']
        if reviews and review['author'] is not None and review['state'] == 'APPROVED'
    }
    reporter = (data.get('author') or {}).get('login')
    pr = PullRequest()
    pr.repository = pull_request_record.repository
    pr.repository_visibility = pull_request_record.pr_visibility
    pr.key = get_pull_request_key(pr.repository, data['number'])
    pr.target = data.get('target')
    pr.source = data.get('source')
    pr.state = data.get('state')
    pr.title = data.get('title')
    pr.is_verified = len(approvers) > 0
    pr.is_approved = is_pr_approved(data)
    pr.url = data.get('weblink')
    pr.approvers = ','.join(sorted(approvers))
    pr.reporter = reporter
    pr.created_on = data.get('createdAt')
    pr.updated_on = data.get('updatedAt')
    pr.organization = pull_request_record.organization
    pr.source_system = GITHUB_SYSTEM
    pr.connection_name = connection_name
    return pr.data()


def is_pr_approved(pr: Dict) -> bool:
    review_decision = pr.get('reviewDecision')
    if review_decision:
        if review_decision == 'APPROVED':
            return True
        return False

    reviews = pr.get('reviews', {}).get('nodes', [])
    approvals = 0

    for review in reviews:
        review_state = review.get('state')
        if review_state == 'CHANGES_REQUESTED':
            return False
        if review_state == 'APPROVED':
            approvals += 1

    return True if approvals > 0 else False


def map_repository_to_laika_object(repository_record, connection_name):
    repository_data = repository_record.repository
    organization_data = repository_record.organization
    repository = Repository()
    repository.name = repository_data['name']
    repository.organization = organization_data
    repository.public_url = repository_data['url']
    repository.is_active = not repository_data['isDisabled']
    repository.is_public = not repository_data['isPrivate']
    repository.updated_at = repository_data['updatedAt']
    repository.created_at = repository_data['updatedAt']
    repository.source_system = GITHUB_SYSTEM
    repository.connection_name = connection_name
    return repository.data()


def map_users_to_laika_object(github_user, connection_name):
    first_name = ''
    last_name = ''
    user_name = github_user.get('name')
    if user_name:
        names = user_name.split(' ')
        if len(names) > 2:
            first_name = names[0]
            last_name = f'{names[1]} {names[2]}'
        elif len(names) == 2:
            first_name = names[0]
            last_name = names[1]
        else:
            first_name = names[0]
    user_lo = User()
    user_lo.id = github_user.get('id')
    user_lo.first_name = first_name
    user_lo.last_name = last_name
    user_lo.email = github_user.get('email')
    user_role: str = github_user.get('role')
    user_lo.is_admin = user_role == 'ADMIN'
    user_lo.title = github_user.get('title')
    user_lo.organization_name = github_user.get('organization_name')
    user_lo.roles = user_role and user_role.capitalize()
    teams = (
        ', '.join(team for team in github_user.get('teams'))
        if github_user.get('teams')
        else ''
    )
    user_lo.groups = teams
    user_lo.mfa_enabled = github_user.get('has_2fa', False)
    user_lo.mfa_enforced = ''
    user_lo.source_system = GITHUB_SYSTEM
    user_lo.connection_name = connection_name
    return user_lo.data()

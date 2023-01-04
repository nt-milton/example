from typing import List, NamedTuple, TypedDict

from objects.system_types import PullRequest, Repository, User

GITHUB_SYSTEM = 'GitHub'


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
        if review['author'] is not None
    }
    reporter = (data.get('author') or {}).get('login')
    pr = PullRequest()
    pr.repository = pull_request_record.repository
    pr.repository_visibility = pull_request_record.pr_visibility
    pr.key = f"{pr.repository}-{data['number']}"
    pr.target = data['target']
    pr.source = data['source']
    pr.state = data['state']
    pr.title = data['title']
    pr.is_verified = len(approvers) > 0
    pr.is_approved = data['reviewDecision'] == 'APPROVED'
    pr.url = data['weblink']
    pr.approvers = ','.join(sorted(approvers))
    pr.reporter = reporter
    pr.created_on = data['createdAt']
    pr.updated_on = data['updatedAt']
    pr.organization = pull_request_record.organization
    pr.source_system = GITHUB_SYSTEM
    pr.connection_name = connection_name
    return pr.data()


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
    if not user_lo.first_name and not user_lo.last_name and not user_lo.email:
        user_lo.first_name = user_lo.title
    return user_lo.data()

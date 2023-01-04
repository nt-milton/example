from integration.azure_devops.constants import AZURE_DEVOPS_SYSTEM
from objects.system_types import PullRequest, Repository, User

NO = 'NO'


def map_users_response_to_laika_object(users_entitlement, connection_name):
    user = users_entitlement.get('user')
    projects_groups_entitlements = [
        entitlement['group']['displayName']
        for entitlement in users_entitlement.get('projectEntitlements', [])
    ]
    groups_entitlements = [
        entitlement['group']['displayName']
        for entitlement in users_entitlement.get('groupAssignments', [])
    ]
    groups = groups_entitlements + projects_groups_entitlements
    lo_user = User()
    lo_user.id = users_entitlement.get('id')
    lo_user.first_name = user.get('displayName')
    lo_user.last_name = NO
    lo_user.email = user.get('principalName')
    lo_user.title = NO
    lo_user.is_admin = NO
    lo_user.mfa_enabled = ''
    lo_user.roles = users_entitlement['accessLevel']['licenseDisplayName']
    lo_user.mfa_enforced = ''
    lo_user.applications = NO
    lo_user.organization_name = users_entitlement['organization']
    lo_user.groups = ', '.join(groups)
    lo_user.connection_name = connection_name
    lo_user.source_system = AZURE_DEVOPS_SYSTEM
    return lo_user.data()


def map_repository_response_to_laika_object(response, connection_name):
    repository = response
    lo_repository = Repository()
    lo_repository.name = repository['name']
    lo_repository.organization = repository['organization']
    lo_repository.public_url = repository['webUrl']
    lo_repository.is_active = not repository['isDisabled']
    lo_repository.is_public = repository['project']['visibility'] == 'public'
    lo_repository.updated_at = NO
    lo_repository.created_at = NO
    lo_repository.connection_name = connection_name
    lo_repository.source_system = AZURE_DEVOPS_SYSTEM
    return lo_repository.data()


def map_pull_request_response_to_laika_object(pull_request, connection_name):
    lo_pull_request = PullRequest()
    approved_by = [
        reviewer['displayName']
        for reviewer in pull_request['reviewers']
        if reviewer['vote'] == 10
    ]
    repository = pull_request['repository']
    lo_pull_request.repository = pull_request['repository']['name']
    lo_pull_request.repository_visibility = repository['project']['visibility']
    lo_pull_request.key = f"{repository['name']}-{pull_request['pullRequestId']}"
    lo_pull_request.target = pull_request['targetRefName']
    lo_pull_request.source = pull_request['sourceRefName']
    lo_pull_request.state = pull_request['status']
    lo_pull_request.title = pull_request['title']
    lo_pull_request.is_verified = NO
    lo_pull_request.is_approved = len(approved_by) > 0
    lo_pull_request.url = pull_request['url']
    lo_pull_request.approvers = ', '.join(approved_by)
    lo_pull_request.reporter = pull_request['createdBy']['displayName']
    lo_pull_request.created_on = pull_request.get('creationDate', '')
    lo_pull_request.updated_on = NO
    lo_pull_request.organization = pull_request['organization']
    lo_pull_request.source_system = AZURE_DEVOPS_SYSTEM
    lo_pull_request.connection_name = connection_name
    return lo_pull_request.data()

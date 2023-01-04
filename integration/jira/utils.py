from integration.exceptions import ConfigurationError
from integration.integration_utils import token_utils
from integration.jira.constants import BROWSE_PROJECTS
from integration.jira.rest_client import (
    get_all_groups,
    get_projects_page,
    get_projects_with_permissions,
    validate_user_permissions,
)
from integration.models import ConnectionAccount


def validate(response: dict, connection_account: ConnectionAccount) -> list:
    fetch_token = token_utils.build_fetch_token(connection_account)
    resources = response['resources']
    validate_administrator_permissions(resources, fetch_token)
    return validate_projects(resources, fetch_token)


def validate_projects(resources: list, fetch_token) -> list:
    projects = get_projects(resources, fetch_token)
    if len(projects) == 0:
        raise ConfigurationError.insufficient_config_data()
    return projects


def validate_administrator_permissions(resources: list, fetch_token):
    for resource in resources:
        cloud_id = resource.get('id', '')
        groups = get_all_groups(cloud_id, fetch_token())
        for group in groups:
            response = validate_user_permissions(
                cloud_id, group.get('groupId', ''), fetch_token()
            )
            if 'privileges' in response.get('errorMessages', [''])[0].split():
                raise ConfigurationError.insufficient_permission()
            else:
                break


def get_projects(resources, fetch_token):
    project_with_permissions = list(
        map(
            lambda project: project['key'],
            get_projects_with_permissions_for_all_resources(
                resources,
                fetch_token,
            ),
        )
    )
    projects = []
    for resource in resources:
        cloud_id = resource.get('id', '')
        for project_response in get_paginated_response_by_api_method(
            get_projects_page, cloud_id, fetch_token
        ):
            if project_response['key'] in project_with_permissions:
                projects.append(project_response)
    return projects


def get_projects_with_permissions_for_all_resources(
    resources,
    fetch_token,
):
    for resource in resources:
        cloud_id = resource['id']
        projects = get_projects_with_permissions(
            cloud_id,
            [BROWSE_PROJECTS],
            fetch_token(),
        )['projects']
        for project in projects:
            yield project


def get_paginated_response_by_api_method(api_method, cloud_id, fetch_token, **kwargs):
    page = 0
    has_next = True
    while has_next:
        has_next, response = api_method(cloud_id, fetch_token(), page=page, **kwargs)
        for item in response:
            yield item
        page = page + 1

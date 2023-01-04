from typing import List

from integration.asana.rest_client import get_projects, get_tickets, get_workspaces
from integration.models import ConnectionAccount
from integration.token import TokenProvider


def get_tickets_projects(
    token_provider: TokenProvider, selected_projects: list, selected_time_range: str
):
    for project in selected_projects:
        for tickets in get_tickets(token_provider, project, selected_time_range):
            yield tickets


def get_projects_with_workspace(access_token: str):
    workspaces = get_workspaces(access_token)
    workspaces_by_id = {}
    for workspace in workspaces:
        workspace_id = workspace.get('gid')
        workspaces_by_id[workspace_id] = workspace
    projects = get_projects(access_token)
    for project in projects:
        workspace_gid: dict = project.get('workspace', {}).get('gid')
        workspace_name = workspaces_by_id.get(workspace_gid, {}).get('name')
        project['workspace'] = dict(name=workspace_name, gid=workspace_gid)
    return projects


def get_selected_projects(
    projects: List, access_token: str, connection_account: ConnectionAccount
) -> List:
    if 'all' not in projects:
        return projects
    new_projects = get_projects(access_token)
    projects_list = [project.get('gid') for project in new_projects]
    connection_account.settings['projects'] = projects_list
    connection_account.save()
    return projects_list


def get_selected_workspaces(
    access_token: str, projects: List, connection_account: ConnectionAccount
):
    selected_projects = get_selected_projects(
        projects, access_token, connection_account
    )
    all_projects_with_workspaces = get_projects_with_workspace(access_token)
    selected_workspaces = set()
    for selected_project in selected_projects:
        selected_workspace = next(
            project.get('workspace', {}).get('gid')
            for project in all_projects_with_workspaces
            if selected_project == project.get('gid')
        )
        selected_workspaces.add(selected_workspace)
    return selected_workspaces

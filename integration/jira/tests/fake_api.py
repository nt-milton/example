from datetime import datetime, timedelta
from pathlib import Path

import jwt
from httmock import HTTMock, urlmatch

from integration.settings import ATLASSIAN_ACCOUNT_CLAIM

UNEXPECTED_API_OPERATION = 'Unexpected operation for Jira fake api'


def fake_jira_api():
    return HTTMock(fake_jira_auth, fake_jira_services)


def fake_jira_api_for_validation():
    return HTTMock(fake_jira_auth, fake_jira_services_for_validation)


def fake_jira_api_expired_token():
    return HTTMock(fake_jira_auth_expired_token, fake_jira_services)


@urlmatch(netloc='auth.atlassian.com')
def fake_jira_auth(url, request):
    access_token_request = b'refresh_token' in request.body
    if access_token_request:
        return f'{{"access_token":"{fake_token()}"}}'
    auth_code_request = b'authorization_code' in request.body
    if auth_code_request:
        return f'{{"access_token":"{fake_token()}", "refresh_token": "refresh_token"}}'
    raise ValueError(UNEXPECTED_API_OPERATION)


@urlmatch(netloc='auth.atlassian.com')
def fake_jira_auth_expired_token(url, request):
    access_token_request = b'refresh_token' in request.body
    if access_token_request:
        return f'{{"access_token":"{fake_expired_token()}"}}'
    auth_code_request = b'authorization_code' in request.body
    if auth_code_request:
        return (
            f'{{"access_token":"{fake_expired_token()}",'
            ' "refresh_token": "refresh_token"}'
        )
    raise ValueError(UNEXPECTED_API_OPERATION)


def load_response(filename):
    with open(Path(__file__).parent / filename, 'r') as file:
        return file.read()


@urlmatch(netloc='api.atlassian.com')
def fake_jira_services(url, request):
    if 'accessible-resources' in url.path:
        return load_response('raw_accessible_resources_response.json')
    elif 'project' in url.path:
        if 'search' in url.path:
            return load_response('raw_projects_response.json')
        elif 'permissions' in url.path:
            return load_response('raw_projects_with_permissions_response.json')
        return load_response('raw_projects_response.json')
    elif 'search' in url.path:
        return load_response('raw_tickets_response.json')
    elif 'users' in url.path:
        return load_response('raw_users_response.json')
    elif 'field' in url.path:
        return load_response('raw_field_response.json')
    elif 'group' in url.path:
        if 'bulk' in url.path:
            return load_response('raw_groups_bulk_response.json')
        elif 'member' in url.path:
            return load_response('raw_users_by_group_response.json')
        else:
            return load_response('raw_groups_response.json')

    raise ValueError(UNEXPECTED_API_OPERATION)


def fake_jira_services_for_validation(url, request):
    if 'accessible-resources' in url.path:
        return load_response('raw_accessible_resources_response.json')
    elif 'project' in url.path:
        if 'search' in url.path:
            return load_response('raw_empty_projects_response.json')
        elif 'permissions' in url.path:
            return '{"projects":[]}'
    elif 'group' in url.path:
        if 'bulk' in url.path:
            return load_response('raw_groups_bulk_response.json')
        elif 'member' in url.path:
            return load_response('raw_empty_users_by_group_response.json')
    raise ValueError(UNEXPECTED_API_OPERATION)


def fake_token():
    encoded_jwt = jwt.encode(
        {
            ATLASSIAN_ACCOUNT_CLAIM: '5f2dc9e0e8c45600228ecd4d',
            'exp': datetime.timestamp(datetime.now() + timedelta(hours=1)),
        },
        'secret',
        algorithm='HS256',
    )
    return encoded_jwt.decode()


def fake_expired_token():
    encoded_jwt = jwt.encode(
        {
            ATLASSIAN_ACCOUNT_CLAIM: '5f2dc9e0e8c45600228ecd4d',
            'exp': datetime.timestamp(datetime.now() + timedelta(minutes=5)),
        },
        'secret',
        algorithm='HS256',
    )
    return encoded_jwt.decode()

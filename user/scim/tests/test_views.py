import json

import pytest
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound

from user.constants import ROLE_ADMIN, ROLE_VIEWER
from user.models import User
from user.scim.tests.mocks import (
    CREATE_USER_BAD_REQUEST,
    CREATE_USER_REQUEST,
    CREATE_USER_REQUEST_BAD_EMAIL,
    CREATE_USER_REQUEST_NO_GROUPS,
    MOCKED_USERNAME,
    PATCH_USER_REQUEST,
    SCIM_EMAIL,
)
from user.tests.factory import create_user

NOT_FOUND_STATUS_CODE = HttpResponseNotFound().status_code
OK_STATUS_CODE = HttpResponse().status_code
BAD_REQUEST_CODE = HttpResponseBadRequest().status_code

SCIM_USER_PATH = '/scim/v2/users'


@pytest.mark.functional(permissions=['user.add_user'])
def test_get_user(graphql_organization, http_client):
    mocked_username = 'testingusername'
    user = create_user(
        graphql_organization,
        email='test_scim@domain.com',
        role=ROLE_ADMIN,
        first_name='john',
        last_name='smith',
        username=mocked_username,
    )
    response = http_client.get(path=f'{SCIM_USER_PATH}/{mocked_username}')
    scim_user = json.loads(response.content.decode("utf-8"))
    assert response.status_code == OK_STATUS_CODE
    assert scim_user['externalId'] == user.username


@pytest.mark.functional(permissions=['user.add_user'])
def test_get_user_not_found(http_client):
    mocked_username = 'nonexistinguser'
    response = http_client.get(path=f'{SCIM_USER_PATH}/{mocked_username}')
    assert response.status_code == NOT_FOUND_STATUS_CODE


@pytest.mark.functional(permissions=['user.add_user'])
def test_create_user(graphql_organization, http_client):
    response = http_client.post(path=SCIM_USER_PATH, data=CREATE_USER_REQUEST)
    scim_user = json.loads(response.content.decode("utf-8"))
    created_user = User.objects.get(email=SCIM_EMAIL)
    assert response.status_code == OK_STATUS_CODE
    assert scim_user['emails'][0]['value'] == SCIM_EMAIL
    assert created_user.username == scim_user['externalId']


@pytest.mark.functional(permissions=['user.add_user'])
def test_create_user_bad_request(graphql_organization, http_client):
    response = http_client.post(path=SCIM_USER_PATH, data=CREATE_USER_BAD_REQUEST)
    assert response.status_code == BAD_REQUEST_CODE


@pytest.mark.functional(permissions=['user.add_user'])
def test_create_user_bad_email(graphql_organization, http_client):
    response = http_client.post(path=SCIM_USER_PATH, data=CREATE_USER_REQUEST_BAD_EMAIL)
    assert response.status_code == BAD_REQUEST_CODE


@pytest.mark.functional(permissions=['user.add_user'])
def test_create_user_no_group(graphql_organization, http_client):
    response = http_client.post(path=SCIM_USER_PATH, data=CREATE_USER_REQUEST_NO_GROUPS)
    scim_user = json.loads(response.content.decode("utf-8"))
    created_user = User.objects.get(email=SCIM_EMAIL)
    assert response.status_code == OK_STATUS_CODE
    assert scim_user['emails'][0]['value'] == SCIM_EMAIL
    assert created_user.username == scim_user['externalId']
    assert created_user.role == ROLE_VIEWER


@pytest.mark.functional(permissions=['user.add_user'])
def test_update_user(graphql_organization, http_client):
    user = User(
        first_name='mock',
        last_name='user',
        email='scim@mockeduser.com',
        username=MOCKED_USERNAME,
    )
    user.save()
    response = http_client.put(
        path=f'{SCIM_USER_PATH}/{MOCKED_USERNAME}', data=CREATE_USER_REQUEST
    )
    scim_user = json.loads(response.content.decode("utf-8"))
    updated_user = User.objects.get(username=CREATE_USER_REQUEST['externalId'])
    assert response.status_code == OK_STATUS_CODE
    assert scim_user['emails'][0]['value'] == CREATE_USER_REQUEST['emails'][0]['value']
    assert updated_user.email == CREATE_USER_REQUEST['emails'][0]['value']
    assert scim_user['name']['familyName'] == CREATE_USER_REQUEST['name']['familyName']
    assert updated_user.last_name == CREATE_USER_REQUEST['name']['familyName']
    assert scim_user['name']['givenName'] == CREATE_USER_REQUEST['name']['givenName']
    assert updated_user.first_name == CREATE_USER_REQUEST['name']['givenName']


@pytest.mark.functional(permissions=['user.add_user'])
def test_patch_user(graphql_organization, http_client):
    username = 'patch1234'
    user = User(
        first_name='mock',
        last_name='user',
        email='scim@mockeduser.com',
        username=username,
    )
    user.save()
    http_client.patch(path=f'{SCIM_USER_PATH}/{username}', data=PATCH_USER_REQUEST)
    assert len(User.objects.filter(username=username)) == 0

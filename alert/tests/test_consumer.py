import pytest
from django.contrib.auth.models import AnonymousUser

from alert.consumer import _should_deny_connection
from organization.tests import create_organization
from user.tests import create_user


@pytest.fixture
def organization():
    return create_organization(flags=[], name='Test Org')


@pytest.fixture
def user(organization):
    return create_user(organization)


@pytest.fixture
def inactive_user(user):
    user.first_name = 'Inactive'
    user.last_name = 'User'
    user.is_active = False
    return user


def test_web_socket_without_user():
    assert _should_deny_connection(None)


def test_web_socket_with_anonymous_user():
    user = AnonymousUser()
    assert _should_deny_connection(user)


@pytest.mark.django_db
def test_web_socket_with_inactive_user(inactive_user):
    assert _should_deny_connection(inactive_user)


@pytest.mark.django_db
def test_web_socket_with_active_user(user):
    assert not _should_deny_connection(user)

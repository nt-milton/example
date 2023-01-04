from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from organization.tests.factory import create_organization
from user.models import MagicLink
from user.tests.factory import create_user

CURRENT_TIME = datetime(2021, 1, 1, tzinfo=timezone.utc)


def create_magic_link(temporary_code='supersimplepassword'):
    user = create_user(organization=create_organization(), email='test@test.com')
    magic_link: MagicLink = MagicLink.objects.create(
        user=user, temporary_code=temporary_code
    )
    return magic_link


@pytest.mark.django_db
def test_get_magic_link_credentials():
    temporary_code = 'supersimplepassword'
    magic_link = create_magic_link(temporary_code)
    email, password = magic_link.temporary_credentials
    assert email == 'test@test.com'
    assert password == temporary_code


@pytest.mark.django_db
def test_get_magic_link_credentials_not_found():
    invalid_token = str(uuid4())
    assert not MagicLink.objects.filter(token=invalid_token).count()


@pytest.mark.django_db
@patch('user.models.timezone')
def test_delete_expired_magic_link(mock_timezone):
    mock_timezone.now.return_value = CURRENT_TIME
    magic_link = create_magic_link()
    MagicLink.objects.filter(token=magic_link.token).update(
        updated_at=CURRENT_TIME - timedelta(days=8)
    )
    magic_link = MagicLink.objects.get(token=magic_link.token)

    magic_links_before_retrieve = MagicLink.objects.count()
    username, password = magic_link.temporary_credentials
    magic_links_after_retrieve = MagicLink.objects.count()

    assert magic_links_before_retrieve == 1
    assert magic_links_after_retrieve == 0
    assert username == 'test@test.com'
    assert password is None


@patch('user.models.get_today', return_value=CURRENT_TIME)
@pytest.mark.django_db
def test_delete_link_when_otp_is_expired(mock_timezone, graphql_user):
    generated_code = '123456'

    link = MagicLink.objects.create(user=graphql_user, temporary_code=generated_code)
    MagicLink.objects.filter(token=link.token).update(
        updated_at=CURRENT_TIME - timedelta(minutes=21)
    )

    link = MagicLink.objects.get(token=link.token)

    assert MagicLink.objects.count() == 1
    email, otp = link.otp_credentials
    mock_timezone.assert_called_once()

    assert email == graphql_user.email
    assert not otp
    assert MagicLink.objects.count() == 0

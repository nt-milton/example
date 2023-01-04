from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest
from django.core.exceptions import ValidationError
from django.core.files import File

from integration.models import validate_email_logo_extension
from integration.tests import create_connection_account
from integration.utils import is_last_execution_within_date_range
from organization.tests import create_organization
from user.constants import ACTIVE
from user.tests import create_user


def test_add_integration_email_logo():
    with pytest.raises(ValidationError):
        file_mock = mock.MagicMock(spec=File)
        # only png file extension
        file_mock.name = 'email_logo.jpg'
        validate_email_logo_extension(file_mock)


def test_validate_interval_without_updated_at():
    within_interval = is_last_execution_within_date_range(None)
    assert within_interval


def test_validate_interval_with_frequency_daily_with_delta_one_day():
    updated_at = datetime.now(timezone.utc) - timedelta(days=1)
    within_interval = is_last_execution_within_date_range(updated_at)
    assert within_interval


def test_validate_interval_with_frequency_daily_not_in_tolerance_range():
    updated_at = datetime.now(timezone.utc) - timedelta(hours=1)
    within_interval = is_last_execution_within_date_range(updated_at)
    assert not within_interval


def test_validate_interval_with_frequency_daily_within_tolerance():
    # Tolerance is 1.5 hours
    updated_at = datetime.now(timezone.utc) - timedelta(hours=22, minutes=30)
    within_interval = is_last_execution_within_date_range(updated_at)
    assert within_interval


@pytest.mark.functional
def test_validate_created_by_different_organization():
    second_organization = create_organization(name='second_organization', state=ACTIVE)
    fake_user = create_user(second_organization, email='fake_user@heylaika.com')
    connection_account = create_connection_account(
        'jira', alias='Connection Account Testing', created_by=fake_user
    )
    assert pytest.raises(ValidationError, connection_account.clean)

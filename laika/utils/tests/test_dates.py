from datetime import timedelta

import pytest
from django.utils import timezone

from laika.utils.dates import validate_timeline_dates
from laika.utils.exceptions import ServiceException


def test_validate_timeline_dates():
    current_date = timezone.now()
    start_date = current_date - timedelta(days=7)
    due_date = current_date - timedelta(days=6)

    with pytest.raises(Exception) as e:
        validate_timeline_dates(start_date, due_date)
    assert "Due date cannot be older than current date" in str(e.value)
    assert e.type == ServiceException

import pytest

from integration.models import Integration
from integration.tests.factory import create_integration


@pytest.mark.django_db
def test_active_exclude_disable():
    create_integration('Integration disabled', metadata={'disabled': True})
    assert len(Integration.objects.actives()) == 0


@pytest.mark.django_db
def test_active_disable_empty():
    create_integration('Integration', metadata={})
    assert len(Integration.objects.actives()) == 1

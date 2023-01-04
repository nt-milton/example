import io

import pytest
from django.core.files import File

from drive.models import DriveEvidence, DriveEvidenceData
from drive.tasks import refresh_drive_cache
from evidence.constants import LAIKA_PAPER


@pytest.fixture
def file():
    return File(name='Laika paper.txt', file=io.BytesIO('This is a test'.encode()))


@pytest.fixture
def drive_evidence(graphql_organization, graphql_user, file):
    drive_evidence_data = DriveEvidenceData(LAIKA_PAPER, file)
    drive_evidence = DriveEvidence.objects.custom_create(
        organization=graphql_organization,
        owner=graphql_user,
        drive_evidence_data=drive_evidence_data,
    )

    return drive_evidence.evidence


@pytest.mark.functional
def test_refresh_cache(drive_evidence, graphql_organization, graphql_user):
    result = refresh_drive_cache.delay(graphql_organization.id, [drive_evidence.id])
    assert result.get()['success'] is True


@pytest.mark.functional
def test_refresh_cache_on_delete(drive_evidence, graphql_organization, graphql_user):
    result = refresh_drive_cache.delay(
        graphql_organization.id, [drive_evidence.id], action='DELETE'
    )
    assert result.get()['success'] is True

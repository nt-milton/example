from datetime import timedelta

import django.utils.timezone as timezone
import pytest

from control.tests.factory import create_control, create_control_evidence
from drive.evidence_handler import create_laika_paper_evidence
from evidence.models import AsyncExportRequest, TagEvidence
from evidence.tests.mutations import (
    CREATE_DOCUMENTS,
    LINK_TAGS,
    UNLINK_TAGS,
    UPDATE_EVIDENCE,
)
from evidence.threads import BulkEvidenceExportThread
from tag.models import Tag

DOC_EXPORT_TYPE = 'DOCUMENTS'


@pytest.fixture
def create_evidences(graphql_client):
    organization, user = graphql_client.context.values()
    evidence1 = create_laika_paper_evidence(organization, user)
    evidence2 = create_laika_paper_evidence(organization, user)
    return evidence1, evidence2


@pytest.fixture
def bulk_evidence_export_sync():
    from evidence.threads import BulkEvidenceExportThread

    BulkEvidenceExportThread.start = lambda self: self.run()


@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_link_tags(graphql_client):
    evidence, tag = create_evidence_tag(graphql_client)
    graphql_client.execute(
        LINK_TAGS, variables={'input': {'evidenceId': evidence.id, 'tagIds': [tag.id]}}
    )

    assert len(TagEvidence.objects.all()) == 1


@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_link_tags_with_organization_id(graphql_client):
    evidence, tag = create_evidence_tag(graphql_client)
    organization, user = graphql_client.context.values()
    graphql_client.execute(
        LINK_TAGS,
        variables={
            'input': {
                'organizationId': organization.id,
                'evidenceId': evidence.id,
                'tagIds': [tag.id],
            }
        },
    )

    assert len(TagEvidence.objects.all()) == 1


@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_unlink_tags(graphql_client):
    evidence, tag = create_evidence_tag(graphql_client)
    executed = graphql_client.execute(
        UNLINK_TAGS,
        variables={'input': {'evidenceId': evidence.id, 'tagIds': [tag.id]}},
    )

    assert executed['data']['unlinkTags']['success'] is True
    assert len(TagEvidence.objects.all()) == 0


@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_unlink_tags_organization_id(graphql_client):
    organization, user = graphql_client.context.values()
    evidence, tag = create_evidence_tag(graphql_client)
    executed = graphql_client.execute(
        UNLINK_TAGS,
        variables={
            'input': {
                'organizationId': organization.id,
                'evidenceId': evidence.id,
                'tagIds': [tag.id],
            }
        },
    )

    assert executed['data']['unlinkTags']['success'] is True
    assert len(TagEvidence.objects.all()) == 0


@pytest.mark.functional(
    permissions=['evidence.add_asyncexportevidence', 'user.view_concierge']
)
def test_create_documents_async_export_request(
    graphql_client, create_evidences, bulk_evidence_export_sync
):
    # Creating test evidence for the drive
    evidence1, evidence2 = create_evidences
    evidence_id = [evidence1.id, evidence2.id]
    variables = {
        'input': {
            'evidenceId': evidence_id,
            'exportType': DOC_EXPORT_TYPE,
            'timeZone': 'US/Eastern',
        }
    }
    graphql_client.execute(CREATE_DOCUMENTS, variables=variables)

    request = AsyncExportRequest.objects.last()
    request_evidence = request.evidence.all()

    assert request.export_type == DOC_EXPORT_TYPE
    assert 'laika-documents' in request.name
    assert len(request_evidence) == 2
    for e in request_evidence:
        assert e.id in evidence_id


def create_evidence_tag(graphql_client):
    organization, user = graphql_client.context.values()
    evidence = create_laika_paper_evidence(organization, user)

    tag = Tag.objects.create(organization=organization, name='Tag Name', is_manual=True)
    return evidence, tag


@pytest.mark.functional(permissions=['evidence.rename_evidence'])
def test_update_evidence(graphql_client):
    organization, user = graphql_client.context.values()
    create_control(
        organization=organization,
        display_id=1,
        name='Control Test',
        description='Testing control',
        implementation_notes='notes',
    )
    control = organization.controls.first()
    create_control_evidence(
        control,
        name='Evidence.txt',
        organization=organization,
    )
    evidence = control.evidence.first()
    assert evidence.description == ''

    expected_description = 'New description'
    graphql_client.execute(
        UPDATE_EVIDENCE,
        variables={
            'input': {'evidenceId': evidence.id, 'description': expected_description}
        },
    )
    evidence = control.evidence.first()
    assert evidence.description == expected_description


@pytest.mark.functional(permissions=['drive.view_driveevidence'])
def test_async_export_request(graphql_client, create_evidences):
    evidence1, _ = create_evidences
    _, user = graphql_client.context.values()

    async_export_request = AsyncExportRequest.objects.create(
        organization=evidence1.organization,
        requested_by=user,
        export_type="DATAROOM",
        time_zone="US/Eastern",
    )
    async_export_request.evidence.set([evidence1])
    export_thread = BulkEvidenceExportThread(
        async_export_request, async_export_request.evidence.all()
    )
    export_thread.run()
    link = async_export_request.link_model

    assert link.time_zone == "US/Eastern"
    assert link.is_expired is False
    assert link.is_enabled is True
    assert link.expiration_date - timezone.localtime(timezone.now()) < timedelta(1)

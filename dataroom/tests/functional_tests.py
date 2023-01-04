import io
import json

import pytest
from django.core.files import File
from graphene.test import Client

from dataroom import evidence_handler
from dataroom.models import Dataroom
from dataroom.tests import create_dataroom_with_evidence
from dataroom.tests.mutations import ADD_FILES_DATAROOM, CREATE_DATAROOM
from dataroom.tests.queries import GET_DATAROOM, GET_DATAROOMS, GET_FILTER_GROUPS
from drive.evidence_handler import create_drive_evidence
from drive.models import DriveEvidence
from evidence import constants
from organization.models import Organization
from user.models import User

TIME_ZONE = 'America/New_York'


@pytest.fixture()
def dataroom(graphql_organization: Organization) -> Dataroom:
    return Dataroom.objects.create(
        organization=graphql_organization, name='Test Dataroom documents'
    )


@pytest.fixture()
def drive_evidence(
    graphql_organization: Organization,
    graphql_user: User,
) -> DriveEvidence:
    template_content = 'My test'
    template_file = File(name='test', file=io.BytesIO(template_content.encode()))
    template = create_drive_evidence(
        graphql_organization, template_file, graphql_user, constants.LAIKA_PAPER
    )
    drive_evidence = DriveEvidence.objects.get(evidence=template)
    drive_evidence.is_template = True
    drive_evidence.save()

    return drive_evidence


def _get_datarooms_response_collection(response):
    return response['data']['datarooms']


@pytest.fixture
def evidence(graphql_user):
    template_content = 'My test'
    template_file = File(name='test', file=io.BytesIO(template_content.encode()))
    template = create_drive_evidence(
        graphql_user.organization, template_file, graphql_user, constants.LAIKA_PAPER
    )
    return template


@pytest.mark.functional(permissions=['dataroom.view_dataroom'])
def test_datarooms_filter_groups(graphql_client):
    response = graphql_client.execute(GET_FILTER_GROUPS)
    filter_groups = response['data']['filterGroupsDatarooms']
    first_filter, *second_filter = filter_groups

    assert len(filter_groups) == 2

    assert first_filter['id'] == 'time'
    assert first_filter['name'] == 'By Time'
    assert first_filter['items'][0]['id'] == 'last_seven_days'
    assert first_filter['items'][1]['id'] == 'last_month'
    assert first_filter['items'][2]['id'] == 'last_quarter'

    assert second_filter[0]['id'] == 'status'
    assert second_filter[0]['name'] == 'By Status'
    assert second_filter[0]['items'][0]['id'] == 'archived'


@pytest.mark.functional(permissions=['dataroom.view_dataroom', 'user.view_concierge'])
def test_get_datarooms_filtered_by_last_seven_days(graphql_client):
    organization, dataroom, evidence_ids = create_dataroom_with_evidence()
    evidence_handler.add_dataroom_documents(
        organization, evidence_ids, dataroom, TIME_ZONE
    )

    response = graphql_client.execute(
        GET_DATAROOMS,
        variables={'filter': json.dumps({"time": "last_seven_days"})},
    )

    collection = _get_datarooms_response_collection(response)
    first_result, *_ = collection

    assert first_result['name'] == dataroom.name
    assert len(collection) == 1


@pytest.mark.functional(
    permissions=['dataroom.add_dataroomevidence', 'user.view_concierge']
)
def test_add_dataroom_document(
    graphql_client: Client,
    graphql_organization: Organization,
    dataroom: Dataroom,
    drive_evidence: DriveEvidence,
):
    response = graphql_client.execute(
        ADD_FILES_DATAROOM,
        variables={
            'input': dict(
                id=dataroom.id,
                documents=drive_evidence.id,
                timeZone='utc',
                organizationId=graphql_organization.id,
            )
        },
    )
    assert len(response['data']['addFilesToDataroom']['documentIds']) == 1


@pytest.mark.functional(
    permissions=['dataroom.add_dataroomevidence', 'user.view_concierge']
)
def test_add_dataroom_document_undeletes_dataroom(
    graphql_client: Client,
    graphql_organization: Organization,
    dataroom: Dataroom,
    drive_evidence: DriveEvidence,
):
    dataroom.is_soft_deleted = True
    dataroom.save()

    response = graphql_client.execute(
        ADD_FILES_DATAROOM,
        variables={
            'input': dict(
                id=dataroom.id,
                documents=drive_evidence.id,
                timeZone='utc',
                organizationId=graphql_organization.id,
            )
        },
    )
    assert len(response['data']['addFilesToDataroom']['documentIds']) == 1

    dataroom_not_deleted = Dataroom.objects.get(id=dataroom.id)
    assert dataroom_not_deleted.is_soft_deleted is False


@pytest.mark.functional(permissions=['dataroom.view_dataroom', 'user.view_concierge'])
def test_get_datarooms_filtered_by_archived(graphql_client: Client, dataroom: Dataroom):
    dataroom.is_soft_deleted = True
    dataroom.save()

    response = graphql_client.execute(
        GET_DATAROOMS, variables={'filter': json.dumps({'status': 'archived'})}
    )

    collection = _get_datarooms_response_collection(response)

    assert len(collection) == 1


@pytest.mark.functional(permissions=['dataroom.add_dataroom'])
def test_create_dataroom(
    graphql_client: Client,
    graphql_organization: Organization,
):
    dataroom_name = 'New Dataroom'
    response = graphql_client.execute(
        CREATE_DATAROOM,
        variables={'input': dict(name=dataroom_name)},
    )
    assert response['data']['createDataroom']['data'] is not None
    created_dataroom = Dataroom.objects.filter(
        name=dataroom_name, organization=graphql_organization
    )
    assert created_dataroom.exists()


@pytest.mark.functional(permissions=['dataroom.add_dataroom'])
def test_create_dataroom_already_exists(
    graphql_client: Client, graphql_organization: Organization, dataroom: Dataroom
):
    dataroom_name = 'Test Dataroom documents'
    response = graphql_client.execute(
        CREATE_DATAROOM,
        variables={'input': dict(name=dataroom_name)},
    )
    assert (
        response['errors'][0].get('message')
        == 'A record with the given name already exists.'
    )


@pytest.mark.functional(permissions=['dataroom.view_dataroom'])
def test_get_dataroom_evidence(graphql_client, graphql_organization, evidence):
    dataroom = Dataroom.objects.create(
        organization=graphql_organization, name='Test Dataroom'
    )
    dataroom.evidence.add(evidence)

    response = graphql_client.execute(GET_DATAROOM, variables={'id': dataroom.id})
    response = response['data']['dataroom']

    assert len(response['evidence']) == 1

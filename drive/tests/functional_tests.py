import datetime
import io
import json

import pytest
from django.core.files import File

from drive.evidence_handler import create_drive_evidence, create_laika_paper_evidence
from drive.models import DriveEvidence
from drive.tests.mutations import ADD_LAIKA_PAPER_IGNORE_WORD
from drive.tests.query import GET_DOCUMENT_FILTERS_QUERY, GET_FILTERED_DOCUMENTS_QUERY
from evidence import constants
from evidence.models import Evidence, IgnoreWord, Language
from laika.utils.get_organization_by_user_type import get_organization_by_user_type
from organization.tests import create_organization

MY_TEST = 'My test'

CREATE_LAIKA_PAPER_INPUT = '''
        mutation ($input: CreateLaikaPaperInput!) {
            createLaikaPaper(input: $input) {
              laikaPaperId
            }
          }
        '''

GET_DRIVE_QUERY = '''
        query (
            $organizationId: UUID,
            $searchCriteria: String,
            $evidenceId: String,
            $filter: JSONString,
            $orderBy: OrderInputType,
            $pagination: PaginationInputType!
        ) {
            drive(
                organizationId: $organizationId
                searchCriteria: $searchCriteria,
                evidenceId: $evidenceId,
                filter: $filter,
                orderBy: $orderBy,
                pagination: $pagination
            ) {
                collection {
                    id
                    name
                    type
                    createdAt
                    updatedAt
                }
            }
        }
    '''


GET_FILTER_GROUPS = '''
        query FilterGroups($organizationId: UUID) {
            filterGroups(organizationId: $organizationId) {
                data {
                    id
                    name
                    items {
                        id
                        name
                        subItems {
                            id
                            name
                            disabled
                        }
                        disabled
                    }
                }
            }
        }
    '''


def _get_drive_evidence_response_collection(response):
    return response['data']['drive']['collection']


@pytest.fixture
def organization():
    organization = create_organization(flags=[])
    return organization


@pytest.mark.functional(permissions=['drive.add_driveevidence', 'user.add_concierge'])
def test_create_laika_paper_empty_content(graphql_client):
    response = graphql_client.execute(CREATE_LAIKA_PAPER_INPUT, variables={'input': {}})

    laika_paper_id = response['data']['createLaikaPaper']['laikaPaperId']
    evidence = Evidence.objects.get(id=laika_paper_id)
    assert evidence.type == constants.LAIKA_PAPER
    assert evidence.file.read().decode('utf-8') == ''


@pytest.mark.functional(permissions=['drive.add_driveevidence', 'user.add_concierge'])
def test_create_laika_paper_empty_content_organization(graphql_client, organization):
    response = graphql_client.execute(
        '''
        mutation ($input: CreateLaikaPaperInput!) {
            createLaikaPaper(input: $input) {
              laikaPaperId
            }
          }
        ''',
        variables={'input': dict(organizationId=organization.id)},
    )

    laika_paper_id = response['data']['createLaikaPaper']['laikaPaperId']
    evidence = Evidence.objects.get(id=laika_paper_id)
    assert evidence.type == constants.LAIKA_PAPER
    assert evidence.file.read().decode('utf-8') == ''


@pytest.mark.functional(permissions=['drive.add_driveevidence', 'user.add_concierge'])
def test_create_laika_paper_from_template(graphql_client):
    organization, user = graphql_client.context.values()
    template_content = MY_TEST
    template_file = File(name='test', file=io.BytesIO(template_content.encode()))
    template = create_drive_evidence(
        organization, template_file, user, constants.LAIKA_PAPER
    )
    de = DriveEvidence.objects.get(evidence=template)
    de.is_template = True
    de.save()

    response = graphql_client.execute(
        CREATE_LAIKA_PAPER_INPUT, variables={'input': dict(templateId=template.id)}
    )

    laika_paper_id = response['data']['createLaikaPaper']['laikaPaperId']
    evidence = Evidence.objects.get(id=laika_paper_id)
    assert evidence.type == constants.LAIKA_PAPER
    assert evidence.file.read().decode('utf-8') == template_content


@pytest.mark.functional(permissions=['drive.add_driveevidence', 'user.add_concierge'])
def test_create_laika_paper_from_template_organization(graphql_client, organization):
    organization, user = graphql_client.context.values()
    template_content = 'My test'
    template_file = File(name='test', file=io.BytesIO(template_content.encode()))
    template = create_drive_evidence(
        organization, template_file, user, constants.LAIKA_PAPER
    )
    de = DriveEvidence.objects.get(evidence=template)
    de.is_template = True
    de.save()

    response = graphql_client.execute(
        '''
        mutation ($input: CreateLaikaPaperInput!) {
            createLaikaPaper(input: $input) {
              laikaPaperId
            }
          }
        ''',
        variables={
            'input': dict(templateId=template.id, organizationId=organization.id)
        },
    )

    laika_paper_id = response['data']['createLaikaPaper']['laikaPaperId']
    evidence = Evidence.objects.get(id=laika_paper_id)
    assert evidence.type == constants.LAIKA_PAPER
    assert evidence.file.read().decode('utf-8') == template_content


@pytest.mark.functional(permissions=['drive.add_driveevidence'])
def test_create_laika_paper_with_non_existing_template(graphql_client):
    non_existing_template = 123
    response = graphql_client.execute(
        CREATE_LAIKA_PAPER_INPUT,
        variables={'input': dict(templateId=non_existing_template)},
    )

    assert response['errors']


@pytest.mark.functional(permissions=['drive.add_driveevidence', 'user.view_concierge'])
def test_add_drive_create_evidence_file(graphql_client):
    import base64

    file_content = base64.b64encode('Drive file'.encode())
    variables = {
        'input': dict(
            timeZone='utc',
            uploadedFiles=[dict(fileName='drive.txt', file=file_content)],
        )
    }

    graphql_client.execute(
        '''
        mutation ($input: AddDriveEvidenceInput!){
            addDriveEvidence(input: $input) {
              evidenceIds
            }
          }
        ''',
        variables=variables,
    )

    assert Evidence.objects.filter(type=constants.FILE).exists()


@pytest.mark.functional(permissions=['drive.add_driveevidence', 'user.view_concierge'])
def test_add_drive_create_evidence_file_with_org_id(graphql_client):
    import base64

    file_content = base64.b64encode('Drive file'.encode())
    organization, user = graphql_client.context.values()
    variables = {
        'input': dict(
            timeZone='utc',
            uploadedFiles=[dict(fileName='drive.txt', file=file_content)],
            organizationId=organization.id,
        )
    }

    graphql_client.execute(
        '''
        mutation ($input: AddDriveEvidenceInput!){
            addDriveEvidence(input: $input) {
              evidenceIds
            }
          }
        ''',
        variables=variables,
    )

    assert Evidence.objects.filter(type=constants.FILE).exists()


@pytest.mark.functional(
    permissions=['drive.change_driveevidence', 'user.change_concierge']
)
def test_update_laika_paper_with_content(graphql_client):
    organization, user = graphql_client.context.values()
    evidence = create_laika_paper_evidence(organization, user)
    new_content = MY_TEST

    graphql_client.execute(
        '''
        mutation ($input: UpdateLaikaPaperInput!) {
            updateLaikaPaper(input: $input) {
              laikaPaperId
            }
          }
        ''',
        variables={
            'input': dict(laikaPaperId=evidence.id, laikaPaperContent=new_content)
        },
    )

    evidence = Evidence.objects.get(id=evidence.id)
    assert evidence.file.read().decode('utf-8') == new_content


@pytest.mark.functional(
    permissions=['drive.change_driveevidence', 'user.change_concierge']
)
def test_update_laika_paper_with_content_organization(graphql_client, organization):
    organization, user = graphql_client.context.values()
    evidence = create_laika_paper_evidence(organization, user)
    new_content = 'My test'

    graphql_client.execute(
        '''
        mutation ($input: UpdateLaikaPaperInput!) {
            updateLaikaPaper(input: $input) {
              laikaPaperId
            }
          }
        ''',
        variables={
            'input': dict(
                laikaPaperId=evidence.id,
                laikaPaperContent=new_content,
                organizationId=organization.id,
            )
        },
    )

    evidence = Evidence.objects.get(id=evidence.id)
    assert evidence.file.read().decode('utf-8') == new_content


@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_drive_query_includes_laika_papers(graphql_client):
    organization, user = graphql_client.context.values()
    laika_paper = create_laika_paper_evidence(organization, user)

    executed = graphql_client.execute(
        GET_DRIVE_QUERY,
        variables={
            'organizationId': None,
            'pagination': dict(page=1, pageSize=10),
        },
    )

    collection = _get_drive_evidence_response_collection(executed)
    first_result, *_ = collection
    assert int(first_result['id']) == laika_paper.id
    assert first_result['type'] == constants.LAIKA_PAPER


@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_get_drive_evidence_filtered_by_last_seven_days(graphql_client):
    organization, user = graphql_client.context.values()
    laika_paper_one = create_laika_paper_evidence(organization, user)
    laika_paper_two = create_laika_paper_evidence(organization, user)
    Evidence.objects.filter(id=laika_paper_two.id).update(
        updated_at=datetime.date.today() - datetime.timedelta(days=8)
    )

    executed = graphql_client.execute(
        GET_DRIVE_QUERY,
        variables={
            'organizationId': None,
            'pagination': dict(page=1, pageSize=10),
            'filter': json.dumps({"time": "last_seven_days"}),
        },
    )

    collection = _get_drive_evidence_response_collection(executed)
    first_result, *_ = collection
    assert int(first_result['id']) == laika_paper_one.id
    assert len(collection) == 1


@pytest.mark.functional(
    permissions=['drive.delete_driveevidence', 'user.view_concierge']
)
def test_delete_drive_evidence(graphql_client):
    organization, user = graphql_client.context.values()
    template_content = MY_TEST
    template_file = File(name='test', file=io.BytesIO(template_content.encode()))
    template = create_drive_evidence(
        organization, template_file, user, constants.LAIKA_PAPER
    )
    de = DriveEvidence.objects.get(evidence=template)
    de.is_template = True
    de.save()

    organization_id = organization.id
    user.role = 'Concierge'

    organization_by_user = get_organization_by_user_type(user, organization_id)

    graphql_client.execute(
        '''
        mutation deleteDriveEvidence($input: DeleteDriveEvidenceInput!) {
            deleteDriveEvidence(input: $input) {
              evidenceIds
            }
        }
        ''',
        variables={
            'input': dict(evidenceIds=de.id, organizationId=organization_by_user.id)
        },
    )

    evidences = Evidence.objects.all()
    assert evidences.count() == 0


@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_drive_query_by_id_includes_laika_papers(graphql_client):
    organization, user = graphql_client.context.values()
    laika_paper = create_laika_paper_evidence(organization, user)

    executed = graphql_client.execute(
        GET_DRIVE_QUERY,
        variables={
            'organizationId': None,
            'evidenceId': laika_paper.id,
            'pagination': dict(page=1, pageSize=1),
        },
    )

    collection = _get_drive_evidence_response_collection(executed)
    first_result, *_ = collection
    assert int(first_result['id']) == laika_paper.id
    assert first_result['type'] == constants.LAIKA_PAPER


@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_drive_filter_groups(graphql_client):
    response = graphql_client.execute(
        GET_FILTER_GROUPS, variables={'organizationId': None}
    )

    filter_groups = response['data']['filterGroups']['data']
    first_result, *others = filter_groups

    assert len(filter_groups) == 2

    assert first_result['id'] == 'time'
    assert first_result['name'] == 'By Time'
    assert first_result['items'][0]['id'] == 'last_seven_days'
    assert first_result['items'][1]['id'] == 'last_month'
    assert first_result['items'][2]['id'] == 'last_quarter'

    assert others[0]['id'] == 'tags'
    assert others[0]['name'] == 'By Tags'
    assert others[0]['items'][0]['id'] == 'playbooks'
    assert others[0]['items'][1]['id'] == 'certificates'
    assert others[0]['items'][2]['id'] == 'tags'


@pytest.mark.functional(permissions=['drive.add_driveevidence'])
def test_add_laika_paper_ignore_word(graphql_client):
    organization, user = graphql_client.context.values()
    evidence = create_laika_paper_evidence(organization, user)
    language, _ = Language.objects.get_or_create(evidence=evidence, code='us_en')
    variables = {
        'input': dict(
            laikaPaperId=evidence.id,
            laikaPaperLanguage=language.code,
            laikaPaperIgnoreWord='word',
        )
    }

    graphql_client.execute(ADD_LAIKA_PAPER_IGNORE_WORD, variables=variables)

    assert IgnoreWord.objects.filter(language=language, word='word').exists()


@pytest.mark.skipif(
    True,
    reason='''Concierge needs to have its own graphql_client
            as in audits and not use the one from LW because the
            authentication will fail''',
)
@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_export_drive(jwt_http_client):
    response = jwt_http_client.get('/evidence/export/test_file.pdf')
    assert response.status_code == 200


@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_get_all_drive_evidence_ids(graphql_client):
    organization, user = graphql_client.context.values()
    create_laika_paper_evidence(organization, user)

    executed = graphql_client.execute(
        '''
        query getAllDriveEvidence(
            $searchCriteria: String
            $filter: JSONString
            $organizationId: String
          ) {
            allDriveEvidence(
              searchCriteria: $searchCriteria
              filter: $filter
              organizationId: $organizationId
            ) {
              ids
            }
          }
        ''',
        variables={'input': dict(searchCriteria='', organizationId=organization.id)},
    )
    assert len(executed['data']['allDriveEvidence']['ids']) == 1


@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_get_document_filters_return_type_and_owner_filters(graphql_client):
    organization, user = graphql_client.context.values()
    create_laika_paper_evidence(organization, user)
    response = graphql_client.execute(GET_DOCUMENT_FILTERS_QUERY)

    filters = response['data']['driveFilters']['data']
    type_filters, owner_filters, tags_filters = filters

    assert len(filters) == 3

    assert len(type_filters['items']) == 1
    assert type_filters['id'] == 'type'
    assert type_filters['category'] == 'Type'
    assert type_filters['items'][0]['id'] == 'LAIKA_PAPER'

    assert owner_filters['id'] == 'owner'
    assert owner_filters['category'] == 'Owner'
    assert owner_filters['items'][0]['id'] == str(user.id)
    assert owner_filters['items'][0]['name'] == user.get_full_name()

    assert tags_filters['id'] == 'tags'
    assert tags_filters['category'] == 'Tags'


@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_filtered_drives_query_return_empty_list(graphql_client):
    """
    Return an empty list when "type" filter is applied with "FILE"
    and there are no documents with that type in database
    """
    organization, user = graphql_client.context.values()
    create_laika_paper_evidence(organization, user)

    response = graphql_client.execute(
        GET_FILTERED_DOCUMENTS_QUERY, variables={'filters': dict(type=constants.FILE)}
    )

    assert response['data']['filteredDrives']['collection'] == list()


@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_filtered_drives_query_return_data(graphql_client):
    """
    Return a list with data when "type" filter is applied with "LAIKA_PAPER"
     and exists laika papers in database
    """
    organization, user = graphql_client.context.values()
    created_document = create_laika_paper_evidence(organization, user)

    response = graphql_client.execute(
        GET_FILTERED_DOCUMENTS_QUERY,
        variables={'filters': dict(type=constants.LAIKA_PAPER)},
    )

    result = response['data']['filteredDrives']['collection']

    assert len(result) == 1

    assert result[0]['type'] == constants.LAIKA_PAPER
    assert result[0]['id'] == str(created_document.id)
    assert result[0]['name'] == created_document.name


@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_filtered_drives_query_by_id(graphql_client):
    """
    Return a document when filter by ID
    """
    organization, user = graphql_client.context.values()
    created_document = create_laika_paper_evidence(organization, user)

    response = graphql_client.execute(
        GET_FILTERED_DOCUMENTS_QUERY,
        variables={'filters': dict(id=created_document.id)},
    )

    result = response['data']['filteredDrives']['collection']

    assert len(result) == 1
    assert result[0]['id'] == str(created_document.id)

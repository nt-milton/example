import pytest

from drive.evidence_handler import create_laika_paper_evidence
from evidence.models import Evidence


@pytest.fixture
def create_evidences(graphql_client):
    organization, user = graphql_client.context.values()
    evidence = create_laika_paper_evidence(organization, user)
    return evidence


def execute_rename_evidences(graphql_client, evidence, name):
    variables = {
        'input': {'evidenceId': evidence.id, 'newName': name, 'sender': 'Drive'}
    }
    graphql_client.execute(
        '''
            mutation renameEvidence($input: RenameEvidenceInput!) {
                renameEvidence(input: $input) {
                    evidence {
                        id
                    }
                }
            }
        ''',
        variables=variables,
    )


@pytest.mark.functional(permissions=['evidence.rename_evidence', 'user.view_concierge'])
def test_rename_evidences_request(graphql_client, create_evidences):
    organization, user = graphql_client.context.values()
    evidence = create_evidences
    execute_rename_evidences(graphql_client, evidence, 'new evidence name')
    evidence_result = Evidence.objects.get(id=evidence.id, organization=organization)
    assert evidence_result.name == 'new evidence name'


@pytest.mark.functional(permissions=['evidence.rename_evidence'])
def test_name_too_long_to_rename_evidences_request(graphql_client, create_evidences):
    organization, user = graphql_client.context.values()
    evidence = create_evidences
    execute_rename_evidences(
        graphql_client,
        evidence,
        'new evidence name new evidence name new evidence name new         evidence'
        ' name new evidence name',
    )

    evidence_result = Evidence.objects.get(id=evidence.id, organization=organization)
    assert evidence_result.name == evidence.name

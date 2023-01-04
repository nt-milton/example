import pytest

from alert.tests.factory import create_evidence
from audit.constants import AUDIT_FIRMS
from audit.tests.factory import create_audit, create_audit_firm
from fieldwork.launchpad import launchpad_mapper
from fieldwork.models import Evidence
from organization.tests import create_organization


@pytest.mark.django_db
def test_evidence_request_launchpad_mapper(graphql_organization):
    audit_one = create_audit(
        organization=graphql_organization,
        name='Laika Dev Soc 2 Type 1 Audit 2021',
        audit_firm=create_audit_firm(AUDIT_FIRMS[0]),
    )

    test_organization = create_organization(flags=[], name='Test Org')
    audit_two = create_audit(
        organization=test_organization,
        name='Laika Dev Soc 2 Type 2 Audit 2021',
        audit_firm=create_audit_firm(AUDIT_FIRMS[1]),
    )

    evidence_one = create_evidence(
        audit_one, display_id='ev-1', name='Ev1', status='open'
    )
    evidence_two = create_evidence(
        audit_one, display_id='ev-2', name='Ev2', status='submitted'
    )
    create_evidence(audit_one, display_id='ev-3', name='Ev3', status='auditor_accepted')
    create_evidence(audit_one, display_id='ev-4', name='Ev4', status='pending')
    create_evidence(audit_two, display_id='ev-5', name='Ev5')

    evidences = launchpad_mapper(Evidence, graphql_organization.id)

    assert len(evidences) == 2

    assert evidences[0].id == f'{audit_one.id}-{evidence_one.id}'
    assert evidences[0].display_id == evidence_one.display_id
    assert evidences[0].name == evidence_one.name
    assert evidences[0].description == audit_one.name
    assert (
        evidences[0].url == f"/audits/{audit_one.id}/evidence-detail/{evidence_one.id}"
    )

    assert evidences[1].id == f'{audit_one.id}-{evidence_two.id}'
    assert evidences[1].display_id == evidence_two.display_id
    assert evidences[1].name == evidence_two.name
    assert evidences[1].description == audit_one.name
    assert (
        evidences[1].url == f"/audits/{audit_one.id}/evidence-detail/{evidence_two.id}"
    )

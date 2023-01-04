import evidence.constants as constants
from evidence.tests import create_evidence
from organization.tests import create_organization


def create_dataroom_with_evidence(dataroom_name='dataroom-test', evidence_types=None):
    if evidence_types is None:
        evidence_types = [
            constants.LAIKA_PAPER,
            constants.FILE,
        ]
    organization = create_organization(name=dataroom_name)
    evidences = create_evidence(organization, evidence_types)
    evidence_ids = evidences.values_list('id', flat=True)
    return (organization, organization.dataroom.first(), evidence_ids)

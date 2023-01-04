import pytest

import evidence.constants as constants
from dataroom import evidence_handler
from dataroom.tests import create_dataroom_with_evidence
from evidence.models import Evidence

TIME_ZONE = 'America/New_York'


@pytest.mark.functional()
def test_add_dataroom_documents():
    organization, dataroom, evidence_ids = create_dataroom_with_evidence()
    evidence_handler.add_dataroom_documents(
        organization, evidence_ids, dataroom, TIME_ZONE
    )
    assert len(dataroom.evidence.all()) == len(evidence_ids)


@pytest.mark.functional()
def test_add_laika_paper_as_pdf():
    organization, dataroom, evidence_ids = create_dataroom_with_evidence()
    laika_paper_ids = Evidence.objects.filter(
        id__in=evidence_ids, type=constants.LAIKA_PAPER
    )
    evidence_handler.add_dataroom_documents(
        organization, laika_paper_ids, dataroom, TIME_ZONE
    )

    assert len(laika_paper_ids) > 0
    assert len(dataroom.evidence.filter(type=constants.LAIKA_PAPER)) == 0

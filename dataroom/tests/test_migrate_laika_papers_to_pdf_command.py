import sys

import pytest

from dataroom.management.commands.migrate_dr_laika_papers_to_pdf import (
    migrate_laika_papers_to_pdf,
)
from dataroom.tests import create_dataroom_with_evidence
from evidence.constants import FILE, LAIKA_PAPER
from evidence.models import Evidence


@pytest.mark.functional()
def test_add_laika_paper_as_pdf():
    _, dataroom, evidence_ids = create_dataroom_with_evidence(
        dataroom_name='dataroom-test',
        evidence_types=[
            LAIKA_PAPER,
            FILE,
        ],
    )
    laika_paper_ids = Evidence.objects.filter(id__in=evidence_ids, type=LAIKA_PAPER)
    migrate_laika_papers_to_pdf(sys.stdout)

    assert len(laika_paper_ids) > 0
    assert len(dataroom.evidence.filter(type=LAIKA_PAPER)) == 0

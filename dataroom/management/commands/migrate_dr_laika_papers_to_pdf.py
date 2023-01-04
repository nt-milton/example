from abc import ABC

from django.core.management.base import BaseCommand

import evidence.constants as constants
from evidence.evidence_handler import create_document_evidence, create_evidence_pdf
from organization.models import Organization

TIME_ZONE = 'UTC'


class Command(BaseCommand, ABC):
    help = 'Migrate all laika papers to a pdf for dataroom'

    def handle(self, *args, **options):
        log = self.stdout

        evidences_migrated = migrate_laika_papers_to_pdf(log)

        for organization_id, dataroom_id, evidence_ids in evidences_migrated:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Migrated Evidence for Organization {organization_id}'
                    f' and Dataroom {dataroom_id}: '
                    f'{evidence_ids}'
                )
            )


def migrate_laika_papers_to_pdf(log):
    evidences_migrated = []

    organizations = Organization.objects.all()
    for organization in organizations:
        all_dr = organization.dataroom.all()

        for dr in all_dr:
            all_dr_evidence = dr.dataroom_evidence.filter(
                evidence__type=constants.LAIKA_PAPER
            ).distinct()

            evidence_ids = []

            for dataroom_evidence in all_dr_evidence:
                evidence = dataroom_evidence.evidence
                file = create_evidence_pdf(evidence)
                new_evidence = create_document_evidence(
                    organization,
                    file.name,
                    constants.FILE,
                    evidence.description,
                    file,
                    TIME_ZONE,
                    overwrite_name=False,
                )
                new_evidence.legacy_evidence = evidence
                new_evidence.save()
                dataroom_evidence.evidence = new_evidence
                dataroom_evidence.save()
                evidence_ids.append(new_evidence.id)
                log.write(f'Evidence {new_evidence.name} migrated')
            if len(evidence_ids) > 0:
                evidences_migrated.append((organization.id, dr.id, evidence_ids))
    return evidences_migrated

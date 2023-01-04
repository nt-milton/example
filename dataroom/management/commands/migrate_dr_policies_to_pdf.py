from abc import ABC

from django.core.files import File
from django.core.management.base import BaseCommand

import evidence.constants as constants
from dataroom.models import DataroomEvidence
from evidence.models import Evidence
from laika.utils.dates import now_date
from organization.models import Organization
from policy.views import get_published_policy_pdf


def get_policy_name(policy, time_zone):
    date = now_date(time_zone, '%Y_%m_%d_%H_%M')
    return f'{policy.name}_{date}.pdf'


class Command(BaseCommand, ABC):
    help = 'Migrate all the policies to a pdf for dataroom'

    def handle(self, *args, **options):
        organizations = Organization.objects.all()
        for organization in organizations:
            all_dr = organization.dataroom.all()

            for dr in all_dr:
                all_dr_evidence = dr.dataroom_evidence.filter(evidence__type='POLICY')
                for dr_evidence in all_dr_evidence:
                    evidence = Evidence.objects.create(
                        name=get_policy_name(
                            policy=dr_evidence.evidence.policy,
                            time_zone='America/New_York',
                        ),
                        description=dr_evidence.evidence.policy.description,
                        organization=organization,
                        type=constants.FILE,
                        file=File(
                            name=dr_evidence.evidence.name,
                            file=get_published_policy_pdf(
                                dr_evidence.evidence.policy.id
                            ),
                        ),
                    )
                    DataroomEvidence.objects.create(evidence=evidence, dataroom=dr)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Organization {organization.id}, '
                            f'Dataroom {dr_evidence.dataroom.name}, '
                            f'Policy evidence: {dr_evidence.evidence.name}'
                        )
                    )
                    dr_evidence.delete()

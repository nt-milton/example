import io
import logging

from django.core.files import File

import evidence.constants as constants
from drive.models import DriveEvidence, DriveEvidenceData
from evidence.models import Evidence, SystemTagLegacyEvidence
from laika.utils.dates import now_date
from policy.models import Policy
from user.models import Team
from user.views import get_team_pdf

logger = logging.getLogger('task_evidence_migration')


# TODO: This will be refactor as part of LK-2441 when all the
# the evidence refactor takes place
def get_team_file(team_id, time_zone):
    team = Team.objects.get(id=team_id)
    pdf = get_team_pdf(team, time_zone)
    date = now_date(time_zone, '%Y_%m_%d_%H_%M')
    file_name = f'{team.name.title()}_{date}.pdf'
    return File(name=file_name, file=io.BytesIO(pdf))


def add_task_policy(organization, task, policies):
    ids = []
    if not policies:
        return ids
    for policy_id in policies:
        policy = Policy.objects.filter(organization=organization, id=policy_id).first()
        if policy:
            evidence, _ = (
                Evidence.objects.filter(
                    name=policy.name, organization=organization, policy_id=policy_id
                )
                .distinct()
                .get_or_create(
                    name=policy.name,
                    organization=organization,
                    policy_id=policy_id,
                    defaults={
                        'description': policy.description,
                        'type': constants.POLICY,
                    },
                )
            )
            task.evidence.add(evidence)
            ids.append(evidence.id)
    return ids


def add_policies_evidence(organization, policies, tag):
    for policy_id in policies:
        policy = Policy.objects.filter(organization=organization, id=policy_id).first()

        if not policy:
            continue

        evidence, _ = Evidence.objects.get_or_create(
            name=policy.name,
            organization=organization,
            policy_id=policy_id,
            defaults={'description': policy.description, 'type': constants.POLICY},
        )

        # Policies should only be tagged and NOT included in DriveEvidence
        SystemTagLegacyEvidence.objects.get_or_create(tag=tag, evidence=evidence)


def add_documents_evidence(organization, documents, tag):
    for document in documents:
        Evidence.objects.link_legacy_document(organization, document, tag)


def add_file_evidence(organization, tag, uploaded_files, user):
    for file in uploaded_files:
        drive_evidence_data = DriveEvidenceData(
            type=constants.FILE, file=file, system_tags_legacy=[tag] if tag else []
        )
        DriveEvidence.objects.custom_create(
            organization=organization,
            owner=user,
            drive_evidence_data=drive_evidence_data,
        )


def add_teams_evidence(time_zone, organization, tag, teams, user):
    if teams:
        tags = {'system_tags_legacy': [tag]} if tag else {}
        DriveEvidence.objects.custom_create_teams(
            organization, time_zone, tags, teams, user
        )


def add_officers_evidence(time_zone, officers, organization, tag, user):
    if officers:
        tags = {'system_tags_legacy': [tag]} if tag else {}
        DriveEvidence.objects.custom_create_officers(
            organization, time_zone, tags, officers, user
        )

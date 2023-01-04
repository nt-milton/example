import itertools
import logging

import evidence.constants as constants
from action_item.evidence_handler import delete_evidence as delete_action_items_evidence
from action_item.models import ActionItem
from control.models import Control, ControlEvidence
from drive.evidence_handler import create_laika_paper_note_evidence
from drive.models import DriveEvidence
from evidence.evidence_handler import (
    create_file_evidence,
    create_officer_evidence,
    create_team_evidence,
    get_copy_source_file,
    get_files_to_upload,
    increment_file_name,
    reference_evidence_exists,
)
from evidence.models import Evidence, SystemTagEvidence, TagEvidence
from evidence.utils import get_evidence_manual_tags
from program.models import SubTask
from tag.models import Tag

logger = logging.getLogger('control_evidence_handler')


# TODO: create a refactor including the ones from vendor and dataroom
# so we remove the code that is so similar, almost duplicated.
def create_control_evidence(
    organization, control, evidence_file, evidence_type=constants.FILE
):
    filters = {'control': control}
    if reference_evidence_exists(
        ControlEvidence, evidence_file.name, evidence_type, filters
    ):
        evidence_file = increment_file_name(
            ControlEvidence, evidence_file, evidence_type, filters
        )
    evidence = create_file_evidence(organization, evidence_file)
    add_evidence_to_control(control, evidence)
    return evidence


def upload_control_file(organization, files, control):
    ids = []
    if not files:
        return ids
    upload_files = get_files_to_upload(files)
    for file in upload_files:
        evidence = create_control_evidence(organization, control, file)
        ids.append(evidence.id)
    return ids


def add_control_documents_or_laika_papers(organization, documents, control, file_type):
    if not documents:
        return []
    all_documents = Evidence.objects.filter(
        organization=organization, id__in=documents, type=file_type
    )

    control.evidence.add(*all_documents)

    for evidence in all_documents:
        evidence.tags.add(*control.tags.all())

        DriveEvidence.objects.update_or_create(
            drive=organization.drive,
            evidence=evidence,
        )
        _ = get_evidence_manual_tags(
            evidence,
            cache_name=f'manual_tags_for_{organization.id}_{evidence.id}',
            force_update=True,
        )

    return [evidence.id for evidence in all_documents]


def add_control_other_evidence(organization, other_evidence_paths, control):
    ids = []
    if not other_evidence_paths:
        return ids
    for other_evidence_path in other_evidence_paths:
        evidence_source_file = get_copy_source_file(organization, other_evidence_path)
        evidence = create_control_evidence(
            organization, control, evidence_source_file, constants.FILE
        )
        ids.append(evidence.id)
    return ids


def add_control_officers(organization, officers, control, time_zone):
    ids = []
    if not officers:
        return ids
    for officer in officers:
        evidence = create_officer_evidence(organization, officer, time_zone)
        add_evidence_to_control(control, evidence)
        ids.append(evidence.id)
    return ids


def add_control_teams(organization, teams, control, time_zone):
    ids = []
    if not teams:
        return ids
    for team_id in teams:
        evidence = create_team_evidence(organization, team_id, time_zone)
        add_evidence_to_control(control, evidence)
        ids.append(evidence.id)
    return ids


def add_control_policy(organization, policies, control, time_zone):
    ids = []
    if not policies:
        return ids
    for policy in policies:
        evidence = Evidence.objects.create_policy(organization, policy, time_zone, True)
        add_evidence_to_control(control, evidence)
        ids.append(evidence.id)
    return ids


def add_evidence_to_control(control, evidence):
    control.evidence.add(evidence)
    organization = control.organization
    evidence.tags.add(*control.tags.all())
    DriveEvidence.objects.update_or_create(
        drive=organization.drive,
        evidence=evidence,
    )
    _ = get_evidence_manual_tags(
        evidence,
        cache_name=f'manual_tags_for_{organization.id}_{evidence.id}',
        force_update=True,
    )
    logger.info(evidence)


def add_note_to_control(organization, user, laika_paper, control):
    if not laika_paper:
        return []

    drive_evidence = create_laika_paper_note_evidence(laika_paper, organization, user)

    return add_control_documents_or_laika_papers(
        organization, [drive_evidence.id], control, constants.LAIKA_PAPER
    )


def delete_evidence(organization, evidence_ids, control):
    action_item_qs = ActionItem.objects.filter(
        evidences__id__in=evidence_ids, evidences__organization=organization
    )

    if action_item_qs.exists():
        for action_item in action_item_qs:
            delete_action_items_evidence(evidence_ids, action_item, organization.id)

    ControlEvidence.objects.filter(
        evidence__id__in=evidence_ids,
        evidence__organization=organization,
        control=control,
    ).delete()

    controls_with_same_evidence = (
        Control.objects.filter(evidence__id__in=evidence_ids)
        .exclude(id=control.id)
        .prefetch_related('tags')
    )

    tags_to_keep = set(
        itertools.chain(
            *[control.tags.all() for control in controls_with_same_evidence]
        )
    )

    tags_to_delete = set(control.tags.all())

    tags_to_delete_on_evidence = tags_to_delete - tags_to_keep

    for evidence in Evidence.objects.filter(id__in=evidence_ids):
        evidence.tags.remove(*tags_to_delete_on_evidence)
        _ = get_evidence_manual_tags(
            evidence,
            cache_name=f'manual_tags_for_{organization.id}_{evidence.id}',
            force_update=True,
        )


def delete_subtask_control_evidence(organization, evidence_id):
    tag = Tag.objects.filter(systemtagevidence__evidence__id=evidence_id).first()
    if tag:
        subtask_id = tag.name
        subtask = SubTask.objects.filter(
            task__program__organization=organization, pk=subtask_id
        ).first()
        if subtask:
            SystemTagEvidence.objects.filter(
                evidence__id=evidence_id, tag__name=str(subtask.id)
            ).delete()
            TagEvidence.objects.filter(
                evidence__id=evidence_id, tag__name=str(subtask.task.category)
            ).delete()


def validate_documents_already_exist(organization, control, documents):
    if len(documents) == 0:
        return []

    return list(
        ControlEvidence.objects.filter(
            evidence__organization=organization,
            evidence_id__in=documents,
            control_id=control.id,
        ).values_list('evidence_id', flat=True)
    )

import itertools
import logging

from django.db.models import Q

import evidence.constants as constants
from control.models import Control
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
from evidence.models import Evidence
from evidence.utils import get_evidence_manual_tags

logger = logging.getLogger('__name__')


def add_control_tags_to_evidence(action_item, documents, organization_id):
    controls = Control.objects.filter(action_items=action_item)

    for control in controls:
        for evidence in documents:
            evidence.tags.add(*control.tags.all())
            _ = get_evidence_manual_tags(
                evidence,
                cache_name=f'manual_tags_for_{organization_id}_{evidence.id}',
                force_update=True,
            )


def create_action_item_evidence(
    organization, action_item, evidence_file, evidence_type=constants.FILE
):
    filters = {'actionitem': action_item}
    ActionItemEvidence = action_item.evidences.through
    if reference_evidence_exists(
        ActionItemEvidence, evidence_file.name, evidence_type, filters
    ):
        evidence_file = increment_file_name(
            ActionItemEvidence, evidence_file, evidence_type, filters
        )
    evidence = create_file_evidence(organization, evidence_file)
    add_evidence_to_action_item(action_item, evidence, organization)
    return evidence


def upload_action_item_file(organization, files, action_item):
    if not files:
        return []
    return [
        create_action_item_evidence(organization, action_item, file).id
        for file in get_files_to_upload(files)
    ]


def add_action_item_documents_or_laika_papers(
    organization, documents, action_item, file_type
):
    if not documents:
        return []
    all_documents = Evidence.objects.filter(
        organization=organization, id__in=documents, type=file_type
    )

    action_item.evidences.add(*all_documents)

    add_control_tags_to_evidence(action_item, all_documents, organization.id)

    for evidence in all_documents:
        DriveEvidence.objects.update_or_create(
            drive=organization.drive,
            evidence=evidence,
        )

    return [evidence.id for evidence in all_documents]


def add_action_item_other_evidence(organization, other_evidence_paths, action_item):
    if not other_evidence_paths:
        return []
    evidence_list = []
    for other_evidence_path in other_evidence_paths:
        evidence_list.append(
            create_action_item_evidence(
                organization,
                action_item,
                get_copy_source_file(organization, other_evidence_path),
                constants.FILE,
            )
        )
    return [evidence.id for evidence in evidence_list]


def add_action_item_officers(organization, officers, action_item, time_zone):
    ids = []
    if not officers:
        return ids
    for officer in officers:
        evidence = create_officer_evidence(organization, officer, time_zone)
        add_evidence_to_action_item(action_item, evidence, organization)
        ids.append(evidence.id)
    return ids


def add_action_item_teams(organization, teams, action_item, time_zone):
    ids = []
    if not teams:
        return ids
    for team_id in teams:
        evidence = create_team_evidence(organization, team_id, time_zone)
        add_evidence_to_action_item(action_item, evidence, organization)
        ids.append(evidence.id)
    return ids


def add_action_item_policy(organization, policies, action_item, time_zone):
    ids = []
    if not policies:
        return ids
    for policy in policies:
        evidence = Evidence.objects.create_policy(organization, policy, time_zone, True)
        add_evidence_to_action_item(action_item, evidence, organization)
        ids.append(evidence.id)
    return ids


def add_evidence_to_action_item(action_item, evidence, organization):
    action_item.evidences.add(evidence)

    controls = Control.objects.filter(action_items=action_item)

    for control in controls:
        evidence.tags.add(*control.tags.all())

    DriveEvidence.objects.update_or_create(
        drive=organization.drive,
        evidence=evidence,
    )
    logger.info(
        f'The evidence id {evidence.id} was added to the action'
        + f'item id {action_item.id}'
    )


def delete_evidence(evidence_ids, action_item, organization_id):
    ActionItemEvidence = action_item.evidences.through
    ActionItemEvidence.objects.filter(
        evidence__id__in=evidence_ids, actionitem=action_item
    ).delete()

    related_controls = Control.objects.filter(
        action_items=action_item
    ).prefetch_related('tags')

    control_tags_to_keep = (
        Control.objects.filter(
            Q(action_items__evidences__id__in=evidence_ids)
            | Q(evidence__id__in=evidence_ids)
        )
        .exclude(action_items=action_item)
        .distinct()
        .prefetch_related('tags')
    )

    # This itertools.chain is used to flatten the list
    tags_to_keep = set(
        itertools.chain(*[control.tags.all() for control in control_tags_to_keep])
    )

    tags_to_delete = set(
        itertools.chain(*[control.tags.all() for control in related_controls])
    )

    tags_to_delete_on_evidence = tags_to_delete - tags_to_keep

    for evidence in Evidence.objects.filter(id__in=evidence_ids):
        evidence.tags.remove(*tags_to_delete_on_evidence)
        _ = get_evidence_manual_tags(
            evidence,
            cache_name=f'manual_tags_for_{organization_id}_{evidence.id}',
            force_update=True,
        )


def add_note_to_action_item(organization, user, laika_paper, action_item):
    if not laika_paper:
        return list()

    drive_evidence = create_laika_paper_note_evidence(laika_paper, organization, user)

    return add_action_item_documents_or_laika_papers(
        organization, [drive_evidence.id], action_item, constants.LAIKA_PAPER
    )

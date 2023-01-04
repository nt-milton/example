import logging

from django.core.files import File

import evidence.constants as constants
from dataroom.models import DataroomEvidence
from evidence.evidence_handler import (
    create_document_evidence,
    create_file_evidence,
    create_officer_evidence,
    create_team_evidence,
    get_copy_source_file,
    get_document_evidence_name,
    get_files_to_upload,
    increment_file_name,
    reference_evidence_exists,
)
from evidence.models import Evidence
from laika.utils.pdf import convert_file_to_pdf

logger = logging.getLogger('dataroom_evidence_handler')


def _validate_and_change_file_name(
    dataroom, evidence_file, evidence_type=constants.FILE
):
    filters = {'dataroom': dataroom}
    if reference_evidence_exists(
        DataroomEvidence, evidence_file.name, evidence_type, filters
    ):
        evidence_file = increment_file_name(
            DataroomEvidence, evidence_file, evidence_type, filters
        )
    return evidence_file


def create_dataroom_evidence(
    organization, dataroom, evidence_file, evidence_type=constants.FILE
):
    evidence_file = _validate_and_change_file_name(
        dataroom, evidence_file, evidence_type
    )
    evidence = create_file_evidence(organization, evidence_file)
    dataroom.evidence.add(evidence)
    return evidence


def upload_dataroom_file(organization, files, dataroom):
    ids = []
    if not files:
        return ids
    upload_files = get_files_to_upload(files)
    for file in upload_files:
        evidence = create_dataroom_evidence(organization, dataroom, file)
        ids.append(evidence.id)
    return ids


def add_dataroom_documents(organization, documents, dataroom, time_zone):
    ids = []
    if not documents:
        return ids
    all_documents = Evidence.objects.filter(organization=organization, id__in=documents)
    for document in all_documents:
        copy_file = File(file=document.file, name=document.name)
        if document.type == constants.FILE:
            copy_file = _validate_and_change_file_name(dataroom, copy_file)
        if document.type == constants.LAIKA_PAPER:
            laika_paper_name = get_document_evidence_name(
                copy_file.name, document.type, time_zone
            )
            copy_file.file = convert_file_to_pdf(copy_file)
            copy_file.name = f'{laika_paper_name}.pdf'
            document.type = constants.FILE
        evidence = create_document_evidence(
            organization,
            copy_file.name,
            document.type,
            document.description,
            copy_file,
            time_zone,
            overwrite_name=False,
        )
        dataroom.evidence.add(evidence)
        ids.append(evidence.id)
    return ids


def add_dataroom_other_evidence(organization, other_evidence_paths, dataroom):
    ids = []
    if not other_evidence_paths:
        return ids
    for other_evidence_path in other_evidence_paths:
        evidence_source_file = get_copy_source_file(organization, other_evidence_path)
        evidence = create_dataroom_evidence(
            organization, dataroom, evidence_source_file, constants.FILE
        )
        ids.append(evidence.id)
    return ids


def add_officers_report_to_dataroom(organization, officers, dataroom, time_zone):
    ids = []
    if not officers:
        return ids
    for officer in officers:
        evidence = create_officer_evidence(organization, officer, time_zone)
        dataroom.evidence.add(evidence)
        ids.append(evidence.id)
    return ids


def add_dataroom_teams(organization, teams, dataroom, time_zone):
    ids = []
    if not teams:
        return ids
    for team_id in teams:
        evidence = create_team_evidence(organization, team_id, time_zone)
        dataroom.evidence.add(evidence)
        ids.append(evidence.id)
    return ids


def add_dataroom_policy(organization, policies, dataroom, time_zone):
    ids = []
    if not policies:
        return ids
    for policy_id in policies:
        evidence = Evidence.objects.create_policy(
            organization, policy_id, time_zone, True
        )
        dataroom.evidence.add(evidence)
        ids.append(evidence.id)
    return ids


def log_delete_file(file_message, dataroom):
    logger.info(f'{file_message} in dataroom {dataroom} deleted successfully')


def delete_evidence(organization, evidence_ids, dataroom):
    DataroomEvidence.objects.filter(
        evidence__id__in=evidence_ids,
        evidence__organization=organization,
        dataroom=dataroom,
    ).delete()

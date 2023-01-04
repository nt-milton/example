import io
import logging
from re import search

from django.core.files import File

import evidence.constants as constants
from drive.models import DriveEvidence
from evidence.evidence_handler import (
    create_file_evidence,
    get_files_to_upload,
    increment_file_name,
    reference_evidence_exists,
)
from evidence.models import TagEvidence
from tag.models import Tag

logger = logging.getLogger('drive_evidence_handler')


def create_drive_evidence(
    organization,
    evidence_file,
    user,
    evidence_type=constants.FILE,
    description='',
    text=None,
):
    filters = {'drive': organization.drive}
    if reference_evidence_exists(
        DriveEvidence, evidence_file.name, evidence_type, filters
    ):
        evidence_file = increment_file_name(
            DriveEvidence, evidence_file, evidence_type, filters
        )
    evidence = create_file_evidence(
        organization, evidence_file, evidence_type, description, text
    )
    DriveEvidence.objects.create(
        drive=organization.drive, evidence=evidence, owner=user
    )

    return evidence


def upload_drive_file(organization, files, user, is_onboarding, description):
    ids = []
    upload_files = get_files_to_upload(files)
    for file in upload_files:
        evidence = create_drive_evidence(
            organization, file, user, description=description
        )
        if is_onboarding:
            tag, _ = Tag.objects.get_or_create(
                organization=organization, name='Onboarding'
            )
            TagEvidence.objects.create(tag=tag, evidence=evidence)

        ids.append(evidence.id)
    return ids


def get_template(template_id):
    dr = DriveEvidence.objects.get(
        evidence__type=constants.LAIKA_PAPER, evidence__id=template_id, is_template=True
    )
    return dr.evidence


def create_laika_paper_evidence(organization, user, template_id=None):
    file = None
    template_name = None
    laika_paper_ext = constants.LAIKA_PAPER_EXTENTION
    prefix = constants.TEMPLATE_PREFIX
    if template_id:
        template = get_template(template_id)
        file = template.file
        template_name = template.name
        if search(prefix, template_name):
            template_name = template_name.replace(prefix, '')

        if not search(laika_paper_ext, template_name):
            template_name = f'{template_name}{laika_paper_ext}'
    else:
        file = open(f'drive/assets/empty{laika_paper_ext}', 'rb')
        template_name = f'Untitled Document{laika_paper_ext}'
    paper_notes_file = File(name=template_name, file=file)
    return create_drive_evidence(
        organization, paper_notes_file, user, constants.LAIKA_PAPER
    )


def create_laika_paper_note_evidence(laika_paper, organization, user):
    file_name = laika_paper.get("laika_paper_title", "")
    file_content = laika_paper.get("laika_paper_content", "")
    laika_paper_ext = constants.LAIKA_PAPER_EXTENTION
    file = io.BytesIO(file_content.encode())
    template_name = f'{file_name}{laika_paper_ext}'
    paper_notes_file = File(name=template_name, file=file)
    drive_evidence = create_drive_evidence(
        organization=organization,
        evidence_file=paper_notes_file,
        user=user,
        evidence_type=constants.LAIKA_PAPER,
        text=file_content,
    )
    return drive_evidence

import base64
import io
import logging
import os
import re
from datetime import datetime

from django.core.files import File

import evidence.constants as constants
from evidence.models import Evidence
from laika.aws.s3 import s3_client
from laika.utils.dates import YYYY_MM_DD_HH_MM, now_date
from laika.utils.pdf import convert_file_to_pdf
from laika.utils.regex import FILE_NAME_EXTENSION
from policy.views import get_published_policy_pdf
from user.models import Officer, Team
from user.views import get_officers_pdf, get_team_pdf

logger = logging.getLogger('evidence_handler')


def reference_evidence_exists(
    reference_model, evidence_file_name, evidence_type, filters
):
    return reference_model.objects.filter(
        **filters, evidence__name=evidence_file_name, evidence__type=evidence_type
    ).exists()


def create_file_evidence(
    organization, upload_file, file_type=constants.FILE, file_description='', text=None
):
    try:
        # Uploaded files are always created due the content could be different
        return Evidence.objects.create(
            organization=organization,
            name=upload_file.name,
            description=file_description,
            type=file_type,
            file=upload_file,
            evidence_text=text,
        )
    except Exception as exc:
        logger.exception(
            f'Error storing file with name {upload_file.name} '
            f'in organization {organization}. Error: {exc}'
        )
        return


def get_document_evidence_name(document_name, document_type, time_zone):
    date = now_date(time_zone, '%Y_%m_%d_%H_%M')
    return (
        f'{get_file_name_without_ext(document_name)}_{date}'
        if document_type == constants.LAIKA_PAPER
        else document_name
    )


def create_document_evidence(
    organization,
    document_name,
    document_type,
    document_description,
    copy_file,
    time_zone,
    overwrite_name=True,
):
    return Evidence.objects.create(
        name=get_document_evidence_name(document_name, document_type, time_zone)
        if overwrite_name
        else document_name,
        description=document_description,
        organization=organization,
        type=document_type,
        file=copy_file,
    )


def create_officer_evidence(organization, officer, time_zone):
    officer_pdf, file_name = create_officer_pdf_evidence(
        organization, officer, time_zone
    )
    evidence, created = Evidence.objects.get_or_create(
        name=file_name,
        description='',
        organization=organization,
        type=constants.OFFICER,
        file=officer_pdf,
    )
    return evidence


def create_team_evidence(organization, team_id, time_zone):
    team = Team.objects.get(organization=organization, id=team_id)
    team_pdf, file_name = create_team_pdf_evidence(team, time_zone)
    evidence, created = Evidence.objects.get_or_create(
        name=file_name,
        description=team.description or '',
        organization=organization,
        type=constants.TEAM,
        file=team_pdf,
    )
    return evidence


def create_officer_pdf_evidence(organization, officer_ids, time_zone):
    try:
        if not officer_ids:
            return None, None

        officers = Officer.objects.filter(organization=organization)
        pdf = get_officers_pdf(officers, time_zone)
        date = now_date(time_zone, '%Y_%m_%d_%H_%M')
        file_name = f'Officers Details_{date}.pdf'

        if not pdf:
            logger.error(
                'Error to generate pdf with officer '
                f'ids {officer_ids} in organization id '
                f'{organization.id}'
            )
            return None, None

        officer_pdf = File(name=file_name, file=io.BytesIO(pdf))
        return officer_pdf, file_name

    except Officer.DoesNotExist:
        logger.warning(f'Officer organization with id {organization.id} does not exist')
        return None, None


def create_team_pdf_evidence(team, time_zone):
    try:
        pdf = get_team_pdf(team, time_zone)
        date = now_date(time_zone, '%Y_%m_%d_%H_%M')
        file_name = f'{team.name}_{date}.pdf'

        if pdf:
            team_pdf = File(name=file_name, file=io.BytesIO(pdf))
            return team_pdf, file_name

    except Team.DoesNotExist:
        logger.warning(f'Team with id {team.id} does not exist')
        return None


# Format of name => name(next_number).extension
# reference_model = Could be LegacyTaskEvidence, DataroomEvidence,
# OrganizationVendorEvidence
# filters = Could task_id, organization_vendor_id, dataroom_id
def increment_file_name(reference_model, evidence_file, evidence_type, filters):
    file_counter = 1
    file_ext = re.search(FILE_NAME_EXTENSION, evidence_file.name).group(0)
    file_name_without_ext = get_file_name_without_ext(evidence_file.name)
    while True:
        # TODO: Refactor this with django contains regex
        file_name = f'{file_name_without_ext}({file_counter}){file_ext}'
        file_counter += 1
        if not reference_evidence_exists(
            reference_model, file_name, evidence_type, filters
        ):
            break
    evidence_file.name = file_name
    return evidence_file


def get_strip_file_name(evidence_type, file_name):
    if evidence_type in [constants.FILE, constants.OFFICER, constants.TEAM]:
        # Due the filename has the extension, we use regex to get
        # the name and do strip
        file_name_without_ext = re.sub(FILE_NAME_EXTENSION, '', file_name)
        file_ext = re.search(FILE_NAME_EXTENSION, file_name).group(0)
        return f'{file_name_without_ext.strip()}{file_ext}'
    return file_name.strip()


def get_copy_source_file(organization, source_evidence_path):
    source_evidence_file = Evidence.objects.filter(
        file=source_evidence_path, organization=organization
    ).first()
    bucket_name = source_evidence_file.file.storage.bucket_name
    key = f'media/private/{source_evidence_path}'

    s3_response_object = s3_client.get_object(Bucket=bucket_name, Key=key)
    response_file = s3_response_object['Body'].read()
    return File(name=source_evidence_file.name, file=io.BytesIO(response_file))


def get_files_to_upload(requested_files):
    files = []
    for requested_file in requested_files:
        if not requested_file:
            continue
        if requested_file.file_name and requested_file.file:
            updated_file = File(
                name=requested_file.file_name,
                file=io.BytesIO(base64.b64decode(requested_file.file)),
            )
            files.append(updated_file)
        else:
            logger.warning(
                f'Not able to create file {requested_file} due missing properties'
            )
    return files


def get_file_name_without_ext(file_name):
    return re.sub(FILE_NAME_EXTENSION, '', file_name)


def update_file_name_with_timestamp(file_name, timestamp=None):
    if not timestamp:
        timestamp = datetime.now()
    file_ext = re.search(FILE_NAME_EXTENSION, file_name).group(0)
    file_name = get_file_name_without_ext(os.path.basename(file_name))
    return f'{file_name}_{timestamp}{file_ext}'


def create_evidence_pdf(evidence):
    file_name = get_timestamp_name(evidence)
    return File(file=convert_file_to_pdf(evidence.file), name=file_name)


def create_policy_pdf(evidence):
    file_name = get_timestamp_name(evidence)
    return File(file=get_published_policy_pdf(evidence.policy_id), name=file_name)


def get_timestamp_name(evidence):
    evidence_name = get_file_name_without_ext(evidence.name)
    date = evidence.updated_at.strftime(YYYY_MM_DD_HH_MM)
    return f'{evidence_name}_{date}.pdf'

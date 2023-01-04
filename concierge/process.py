import logging
import os
import time
from collections import defaultdict
from shutil import make_archive, rmtree

import boto3
import botocore
import pdfkit
from django.db import connection

from laika.aws.ses import send_email
from laika.celery import app as celery_app
from laika.settings import (
    AWS_PRIVATE_MEDIA_LOCATION,
    ENVIRONMENT,
    LAIKA_CONCIERGE_REDIRECT,
    NO_REPLY_EMAIL,
)

from .constants import EVIDENCE_DIRECTORY
from .sql.playbook_evidence import SQL_QUERY_PLAYBOOK_EVIDENCE

s3 = boto3.client('s3')

logging.basicConfig(level=os.getenv('LAIKA_CLI_LOG_LEVEL', logging.ERROR))
logger = logging.getLogger(__name__)

LAIKA_PAPER_EXTENSION = 'laikapaper'
DOCUMENTS = 'DOCUMENTS'
POLICY = 'POLICY'


def query_for_playbook(organization_id, playbooks):
    placeholders = ', '.join(['%s'] * len(playbooks))
    query = SQL_QUERY_PLAYBOOK_EVIDENCE.format(placeholders)
    with connection.cursor() as cursor:
        cursor.execute(query, [organization_id] + playbooks + [organization_id])
        results = cursor.fetchall()
    framework = defaultdict(list)
    for evidence_type, framework_name, category_name, evidence_file in results:
        framework[evidence_type, framework_name, category_name].append(evidence_file)
    return framework


def convert_laikapaper_to_pdf(source_filename, output_filename, organization_id, email):
    try:
        pdfkit.from_file(source_filename, output_filename)
    except IOError:
        logger.info(
            f'Organization: {organization_id}, User: {email}, '
            f'Failed to convert file {source_filename}'
        )
    finally:
        os.remove(source_filename)


def create_pdf_path(final_path, organization_id, email):
    logger.info(
        f'Organization: {organization_id}, User: {email}, '
        'Found a laikapaper! {final_path}'
    )
    logger.info(f'Organization: {organization_id}, User: {email}, Converting to pdf...')
    separator = '.'
    splitted_path = final_path.split(separator)
    splitted_path[-1] = 'pdf'
    final_pdf_path = separator.join(splitted_path)
    convert_laikapaper_to_pdf(final_path, final_pdf_path, organization_id, email)


def download_evidences(program_path, path, counter, organization_id, email):
    os.makedirs(program_path, exist_ok=True)
    extension = path.split('.')[-1]
    cropped_path = f'evidence_{counter}.{extension}' if (len(path) > 240) else path
    final_path = os.path.join(program_path, os.path.basename(cropped_path))
    try:
        s3.download_file(
            f'laika-app-{ENVIRONMENT}',
            f'{AWS_PRIVATE_MEDIA_LOCATION}/{path}',
            final_path,
        )
        if extension.lower() == LAIKA_PAPER_EXTENSION:
            create_pdf_path(final_path, organization_id, email)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            logger.info(
                f'The object laika-app-{ENVIRONMENT}/'
                f'{AWS_PRIVATE_MEDIA_LOCATION}/{path} does not exist.'
            )
        elif e.response['Error']['Code'] == '403':
            logger.info(
                f'No permissions to download laika-app-{ENVIRONMENT}'
                f'/{AWS_PRIVATE_MEDIA_LOCATION}/{path}'
            )
        else:
            logger.info(
                f'Error downloading laika-app-{ENVIRONMENT}/'
                f'{AWS_PRIVATE_MEDIA_LOCATION}/{path}'
            )


def create_evidence_folder(
    output_directory='evidence',
    evidence_type='evidence',
    certification_name='evidence',
    category_name='evidence',
):
    if evidence_type == POLICY:
        playbook_path = os.path.join(output_directory, evidence_type)
    else:
        playbook_path = os.path.join(
            output_directory, evidence_type, certification_name, category_name
        )
    return playbook_path


def download_certification_evidence(
    framework, output_directory, organization_id, email
):
    logger.info(framework)
    certification_category, paths = framework
    counter = 0
    if not certification_category or not paths:
        return
    logger.info(f'Downloading evidence for framework {certification_category}...')
    evidence_type, certification_name, category_name = certification_category
    if evidence_type == DOCUMENTS and (not certification_name or not category_name):
        return
    for path in paths:
        if not path:
            continue
        counter = counter + 1
        logger.info(
            f'Organization: {organization_id}, User: {email}, '
            f'Downloading evidence file {path}...'
        )
        playbook_path = create_evidence_folder(
            output_directory, evidence_type, certification_name, category_name
        )
        download_evidences(playbook_path, path, counter, organization_id, email)


@celery_app.task(name='Export DDP Pulldown')
def export(organization_id, playbooks, email):
    ts = time.time()
    directory_name = f'{organization_id}{ts}'
    output_directory = f'{EVIDENCE_DIRECTORY}/{directory_name}'
    os.makedirs(output_directory, exist_ok=True)
    frameworks = query_for_playbook(organization_id, playbooks).items()

    for framework in frameworks:
        download_certification_evidence(
            framework, output_directory, organization_id, email
        )
    try:
        make_archive(output_directory, 'zip', output_directory)
    except IOError:
        logger.info(f'Cannot create file {output_directory}.zip')

    s3_file_name = f'{AWS_PRIVATE_MEDIA_LOCATION}/evidence-ddp/{directory_name}'

    with open(f'{output_directory}.zip', 'rb') as f:
        s3.upload_fileobj(f, f'laika-app-{ENVIRONMENT}', s3_file_name)

    rmtree(output_directory)
    os.remove(f'{output_directory}.zip')
    template_context = {
        'url': (
            f'{LAIKA_CONCIERGE_REDIRECT}/organizations/{organization_id}/'
            f'ddp_download?download={directory_name}'
        )
    }

    send_email(
        subject='Your DDP Pulldown is ready!',
        from_email=NO_REPLY_EMAIL,
        to=[email],
        template='ddp_pulldown_ready.html',
        template_context=template_context,
    )

import logging
from typing import List

import boto3

from drive.utils import trigger_drive_cache
from evidence.models import Evidence
from laika.celery import app as celery_app
from laika.settings import AWS_PRIVATE_MEDIA_LOCATION, ENVIRONMENT
from organization.models import Organization

logger = logging.getLogger('drive_tasks')
BUCKET = f'laika-app-{ENVIRONMENT}'


def delete_evidence_from_boto(key):
    boto3.client('s3').delete_object(Bucket=BUCKET, Key=key)


@celery_app.task(name='Delete Evidence From S3')
def delete_evidences_from_s3(filenames: List[str]):
    logger.info(f'Delete files: {filenames}')

    for filename in filenames:
        key = f'{AWS_PRIVATE_MEDIA_LOCATION}/{filename}'
        try:
            logger.info(f'Deleting evidence from S3: {filename}')
            delete_evidence_from_boto(key)
        except Exception as e:
            logger.warning(f'Error deleting evidence from s3: {e}')
    return {'success': True}


@celery_app.task(name='Cache drive tags')
def refresh_drive_cache(*args, **kwargs):
    organization = Organization.objects.get(id=args[0])

    try:
        evidences = []
        if args[1]:
            evidences = Evidence.objects.filter(id__in=args[1])

        return trigger_cache_update(organization, evidences)
    except Exception as e:
        logger.error(
            f'Error refreshing drive {organization.drive.id} cache with evidence id'
            f' {args[1]}. {e} '
        )


def trigger_cache_update(organization, evidences, action='CREATE'):
    logger.info(f'Updating cache for drive {organization.drive.id}')
    trigger_drive_cache(organization, evidences, action=action)

    logger.info(f'Cache successfully updated for  {organization.drive.id}')
    return {'success': True}

import logging
import os

import boto3
import botocore
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET

from laika.decorators import concierge_service
from laika.settings import AWS_PRIVATE_MEDIA_LOCATION, ENVIRONMENT

from .process import export

logger = logging.getLogger(__name__)


@require_GET
@concierge_service(
    permission='user.view_concierge',
    exception_msg='Failed to get programs. Please try again.',
    revision_name='Programs retrieved',
)
def export_ddp(request, organization_id):
    try:
        playbooks_param = request.GET.get('playbooks')
        playbooks = playbooks_param.split(',')
        email = request.user.email
        export.delay(organization_id, playbooks, email)

        return HttpResponse('DDP Exported')
    except KeyError:
        return HttpResponseBadRequest


@concierge_service(
    permission='user.view_concierge',
    exception_msg='Failed to get programs. Please try again.',
    revision_name='DDP downloaded',
)
def download_ddp(request, directory_name):
    s3 = boto3.client('s3')
    file_path = f'{directory_name}.zip'

    try:
        s3.download_file(
            f'laika-app-{ENVIRONMENT}',
            f'{AWS_PRIVATE_MEDIA_LOCATION}/evidence-ddp/{directory_name}',
            file_path,
        )
        with open(file_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/zip")
            response[
                'Content-Disposition'
            ] = f'inline; filename={os.path.basename(file_path)}'

        os.remove(file_path)

        return response
    except botocore.exceptions.ClientError as e:
        error_message = e.response['Error']['Message']
        logger.info(f'Failed to download {directory_name}: {error_message}')
        return HttpResponseBadRequest

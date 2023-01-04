import json
import logging

from django.http.response import HttpResponse
from django.views.decorators.http import require_GET

from dataroom.models import Dataroom
from evidence.constants import LEGACY_DOCUMENT
from laika.auth import login_required
from laika.aws.s3 import legacy_s3_client
from laika.utils.pdf import get_document_pdf
from policy.views import export_policy

S3_FILE = 'S3File'
DOCUMENT = 'Document'
POLICY_TYPE = 'Policy'


logger = logging.getLogger('export_documents')


@require_GET
@login_required
def export_dataroom(request, dataroom_id):
    dataroom = Dataroom.objects.get(
        organization=request.user.organization, id=dataroom_id
    )
    if dataroom:
        zip_buffer = dataroom.evidence.all().exclude(type=LEGACY_DOCUMENT).export()
        response = HttpResponse(zip_buffer, content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="%s"' % dataroom.name
        return response
    return None


def export_document(request):
    body = request.body.decode('utf-8')
    body_obj = json.loads(body)
    document_id = body_obj['id']
    pdf = get_document_pdf(request.user.organization, document_id)

    response = HttpResponse(pdf, content_type='application/pdf')
    name = body_obj['name']
    response['Content-Disposition'] = f'attachment;filename="{name}.pdf"'
    return response


def get_s3_file(request):
    body = request.body.decode('utf-8')
    body_obj = json.loads(body)

    s3_response_object = legacy_s3_client.get_object(
        Bucket=f'org-{request.user.organization.id}', Key=body_obj['id']
    )
    return s3_response_object['Body'].read()


def export_s3_file(request):
    body = request.body.decode('utf-8')
    body_obj = json.loads(body)
    filename = body_obj['filename']
    object_content = get_s3_file(request)

    response = HttpResponse(object_content, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment;filename="{filename}"'
    return response


@login_required
def export_dataroom_document(request):
    body = request.body.decode('utf-8')
    body_obj = json.loads(body)

    if body_obj['__typename'] == DOCUMENT:
        return export_document(request)

    elif body_obj['__typename'] == S3_FILE:
        return export_s3_file(request)

    elif body_obj['__typename'] == POLICY_TYPE:
        return export_policy(body_obj['id'])

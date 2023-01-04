import json
import logging

from django.http.response import HttpResponse
from django.views.decorators.csrf import csrf_exempt

import evidence.constants as constants
from laika.auth import login_required
from program.models import ArchivedEvidence

logger = logging.getLogger('export_evidence')


def export_file(file, file_name, content_type='application/pdf', file_type='pdf'):
    response = HttpResponse(file, content_type=content_type)
    if file_type != '':
        response[
            'Content-Disposition'
        ] = f'attachment;filename="{file_name}.{file_type}"'
    else:
        response['Content-Disposition'] = f'attachment;filename="{file_name}"'
    return response


@csrf_exempt
@login_required
def bulk_export_evidence(request):
    body_obj = json.loads(request.body.decode('utf-8'))
    evidence_ids = body_obj['evidenceIds']
    zip_buffer = ArchivedEvidence.objects.filter(
        organization=request.user.organization, id__in=evidence_ids
    ).export()
    response = HttpResponse(zip_buffer, content_type='application/zip')
    response['Content-Disposition'] = 'attachment;'
    return response


def display_error_message(evidence_id, organization):
    logger.warning(
        f'Archived Evidence id not found {evidence_id} for organization: {organization}'
    )
    return HttpResponse('Evidence not found', status=404)


@csrf_exempt
@login_required
def export_evidence(request):
    body_obj = json.loads(request.body.decode('utf-8'))
    evidence_id = body_obj['id']
    organization = request.user.organization
    try:
        evidence = ArchivedEvidence.objects.get(
            id=evidence_id, organization=organization
        )
    except ArchivedEvidence.DoesNotExist:
        return display_error_message(evidence_id, organization)

    if evidence.type != constants.FILE:
        return display_error_message(evidence_id, organization)

    return export_file(evidence.file, evidence.name, 'application/octet-stream', '')

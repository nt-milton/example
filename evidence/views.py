import json
import logging

from django.http.response import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

import evidence.constants as constants
from evidence.models import Evidence
from laika.aws import dynamo
from laika.backends.concierge_backend import ConciergeAuthenticationBackend
from laika.backends.laika_backend import AuthenticationBackend
from laika.decorators import service
from laika.utils.get_organization_by_user_type import get_organization_by_user_type
from laika.utils.pdf import convert_html_text_to_pdf
from policy.views import export_policy

logger = logging.getLogger('export_evidence')


def get_document_pdf(organization, document_id):
    html_text = dynamo.get_document(organization.id, f'd-{document_id}')
    return convert_html_text_to_pdf(html_text)


def export_file(file, file_name, content_type='application/pdf', file_type='pdf'):
    response = HttpResponse(file, content_type=content_type)
    if file_type != '':
        response[
            'Content-Disposition'
        ] = f'attachment;filename="{file_name}.{file_type}"'
    else:
        response['Content-Disposition'] = f'attachment;filename="{file_name}"'
    return response


def get_evidence_id(request):
    body_obj = json.loads(request.body.decode('utf-8'))
    return body_obj.get('id')


def get_organization_id(request):
    body_obj = json.loads(request.body.decode('utf-8'))
    return body_obj.get('organizationId')


@csrf_exempt
@service(
    allowed_backends=[
        {
            'backend': ConciergeAuthenticationBackend.BACKEND,
            'permission': 'user.view_concierge',
        },
        {
            'backend': AuthenticationBackend.BACKEND,
            'permission': 'drive.view_driveevidence',
        },
    ],
    exception_msg='Failed to download evidence',
)
def export_evidence(request):
    evidence_id = get_evidence_id(request)
    if not evidence_id:
        return HttpResponseBadRequest()

    organization = get_organization_by_user_type(
        request.user, get_organization_id(request)
    )
    evidence = Evidence.objects.get(id=evidence_id, organization=organization)

    if evidence.type in (constants.FILE, constants.OFFICER, constants.TEAM):
        return export_file(evidence.file, evidence.name, 'application/octet-stream', '')

    elif evidence.type == constants.LAIKA_PAPER:
        pdf = convert_html_text_to_pdf(evidence.file.read().decode('utf-8'))
        return export_file(pdf, evidence.name)

    elif evidence.type == constants.POLICY:
        if evidence.policy:
            return export_policy(evidence.policy.id)
        response = HttpResponse(evidence.file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment;filename="{evidence.name}.pdf"'

        return response

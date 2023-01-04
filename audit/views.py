import json
import logging

from django.http.response import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

from audit.models import Audit
from audit.tasks import export_audit
from audit.utils.audit import get_current_status, get_report_file
from laika.decorators import audit_service, laika_service
from laika.utils.exceptions import ServiceException
from laika.utils.files import get_file_extension

logger = logging.getLogger(__name__)


def get_audit_report(audit, report_field=None):
    audit_status = audit.status.first()
    current_status = get_current_status(audit_status)

    report = get_report_file(
        audit=audit, current_status=current_status, report_field=report_field
    )
    file_extension = get_file_extension(str(report.file))

    return report, file_extension


@csrf_exempt
@laika_service(
    atomic=False,
    permission='audit.view_audit',
    exception_msg='Could not download audit report',
)
def download_report(request):
    body_obj = json.loads(request.body.decode('utf-8'))
    audit_id = body_obj.get('id')

    if not audit_id:
        return HttpResponseBadRequest()

    audit = Audit.objects.get(id=audit_id)
    report, file_extension = get_audit_report(audit)

    response = HttpResponse(report, content_type='application/octet-stream')
    file_name = f'{audit.name}{file_extension}'
    response['Content-Disposition'] = f'attachment;filename="{file_name}"'

    return response


@csrf_exempt
@audit_service(
    atomic=False,
    permission='audit.view_audit',
    exception_msg='Could not download audit report',
)
def download_report_from_auditor(request):
    body_obj = json.loads(request.body.decode('utf-8'))
    audit_id = body_obj.get('id')
    report_field = body_obj.get('field')

    if not audit_id:
        return HttpResponseBadRequest()

    audit = Audit.objects.get(id=audit_id)
    report, file_extension = get_audit_report(audit, report_field=report_field)

    response = HttpResponse(report, content_type='application/octet-stream')
    file_name = f'{audit.name}{file_extension}'
    response['Content-Disposition'] = f'attachment;filename="{file_name}"'

    return response


@csrf_exempt
@audit_service(
    atomic=False,
    permission='audit.view_audit',
    exception_msg='Unable to generate audit history file',
)
def generate_audit_history_file(request):
    body_obj = json.loads(request.body.decode('utf-8'))
    audit_id = body_obj.get('id')
    try:
        auditor_user = request.user

        if not audit_id:
            return HttpResponseBadRequest()

        export_audit(audit_id, auditor_user)

        return HttpResponse({}, content_type='application/json')
    except Exception as e:
        logger.exception(f'Error trying to generate audit {audit_id} history: {e}')
        raise ServiceException('Failed to generate audit history file')

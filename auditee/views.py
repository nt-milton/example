import json

from django.http.response import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from audit.models import Audit
from laika.decorators import laika_service
from laika.utils.files import get_file_extension


@csrf_exempt
@require_POST
@laika_service(
    atomic=False,
    permission='audit.view_audit',
    exception_msg='Failed to get audit uploaded draft report PDF.',
    revision_name='Get audit uploaded draft report PDF',
)
def get_uploaded_draft_report(request):
    body_obj = json.loads(request.body.decode('utf-8'))
    audit_id = body_obj.get('auditId')
    organization_id = body_obj.get('organizationId')

    audit = Audit.objects.get(id=audit_id, organization__id=organization_id)

    audit_status = audit.status.first()
    draft_report = audit_status.draft_report

    file_extension = get_file_extension(str(draft_report.file))

    response = HttpResponse(draft_report, content_type='application/octet-stream')
    file_name = f'{audit.name}{file_extension}'
    response['Content-Disposition'] = f'attachment;filename="{file_name}"'

    return response

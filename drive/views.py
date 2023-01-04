import json

from django.http.response import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from evidence.models import Evidence
from laika.backends.concierge_backend import ConciergeAuthenticationBackend
from laika.backends.laika_backend import AuthenticationBackend
from laika.constants import MAX_DOWNLOAD_FILES
from laika.decorators import service
from laika.utils.exceptions import ServiceException
from user.constants import CONCIERGE


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
    exception_msg='Failed to generate bulk evidence export',
    revision_name='Bulk evidence export',
)
def export_drive(request):
    body_obj = json.loads(request.body.decode('utf-8'))
    evidence_ids = body_obj['evidenceIds']

    if len(evidence_ids) > MAX_DOWNLOAD_FILES:
        raise ServiceException('Too many files selected for download.')

    if request.user.role == CONCIERGE:
        organization_id = body_obj['organizationId']
    else:
        organization_id = request.user.organization.id

    zip_buffer = Evidence.objects.filter(
        organization_id=organization_id, id__in=evidence_ids
    ).export()

    response = HttpResponse(zip_buffer, content_type='application/zip')
    response['Content-Disposition'] = 'attachment;'
    return response

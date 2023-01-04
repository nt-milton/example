import logging
import os

from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET

from blueprint.models import EvidenceMetadataBlueprint
from laika.auth import login_required

logger = logging.getLogger(__name__)


@require_GET
@login_required
def download_evidence_metadata(request, evidence_metadata_id):
    try:
        metadata = EvidenceMetadataBlueprint.objects.get(id=evidence_metadata_id)
        _, file_extension = os.path.splitext(metadata.attachment.name)
        filename = f'ExampleEvidence_{metadata.reference_id}{file_extension}'
        response = HttpResponse(
            metadata.attachment, content_type='application/octet-stream'
        )
        response['Content-Disposition'] = f'attachment;filename="{filename}"'
        response['Access-Control-Expose-Headers'] = 'Content-Disposition'
        return response
    except EvidenceMetadataBlueprint.DoesNotExist:
        logger.error(f'The document with the id {evidence_metadata_id} does not exist')
        return HttpResponseBadRequest()

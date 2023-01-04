import tempfile

from django.core.files import File

from fieldwork.models import Attachment, Evidence, TemporalAttachment


def create_evidence_request(audit):
    return Evidence.objects.create(
        audit=audit, display_id='2', name='Ev2', instructions='yyyy', status='open'
    )


def create_tmp_attachment_factory(fetch_logic, name):
    return TemporalAttachment.objects.create(
        name=name,
        file=File(file=tempfile.TemporaryFile(), name=name),
        fetch_logic=fetch_logic,
        audit=fetch_logic.audit,
    )


def create_evidence_attachment(evidence_request, file, filename, from_fetch=True):
    return Attachment.objects.create(
        evidence=evidence_request, name=filename, file=file, from_fetch=from_fetch
    )

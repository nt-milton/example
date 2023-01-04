import tempfile

from django.core.files import File

from evidence.models import Evidence


def create_evidence(organization, evidence_types=[], file_ext=''):
    """Build a list of evidences"""
    for index, evidence_type in enumerate(evidence_types):
        file_name = f'file-test-{evidence_type}-{index}{file_ext}'
        Evidence.objects.create(
            name=file_name,
            description='',
            organization=organization,
            type=evidence_type,
            file=File(file=tempfile.TemporaryFile(), name=file_name),
        )
    return Evidence.objects.all()

from django.db import models

from laika.storage import PublicMediaStorage


def evidence_metadata_attachments_directory_path(instance, filename):
    return f'blueprint/evidences_metadata/{instance.reference_id}/{filename}'


class EvidenceMetadataBlueprint(models.Model):
    class Meta:
        verbose_name_plural = 'Evidences Metadata Blueprint'

    reference_id = models.CharField(max_length=255)
    airtable_record_id = models.CharField(blank=True, max_length=512)
    name = models.CharField(blank=True, max_length=255)
    description = models.TextField(blank=True)
    attachment = models.FileField(
        storage=PublicMediaStorage(),
        max_length=1024,
        upload_to=evidence_metadata_attachments_directory_path,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

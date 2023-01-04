from django.db import models

from laika.storage import PublicMediaStorage


def control_family_illustration_directory_path(instance, filename):
    return f'family/{instance.name}/{filename}'


class ControlFamilyBlueprint(models.Model):
    class Meta:
        unique_together = (('name', 'acronym'),)
        verbose_name_plural = 'Control Family Blueprint'

    airtable_record_id = models.CharField(blank=True, max_length=512)
    name = models.CharField(unique=True, max_length=255)
    acronym = models.CharField(max_length=20)

    description = models.CharField(blank=True, max_length=255)

    illustration = models.FileField(
        storage=PublicMediaStorage(),
        max_length=1024,
        upload_to=control_family_illustration_directory_path,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name}'

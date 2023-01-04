from django.db import models

from laika.constants import CATEGORIES
from laika.storage import PublicMediaStorage


def training_file_directory_path(instance, filename):
    return f'blueprint/trainings/{filename}'


class TrainingBlueprint(models.Model):
    class Meta:
        verbose_name_plural = 'Trainings Blueprint'

    name = models.TextField(unique=True, max_length=200)
    airtable_record_id = models.CharField(blank=True, max_length=512)
    category = models.CharField(max_length=100, choices=CATEGORIES)
    description = models.TextField()
    file_attachment = models.FileField(
        storage=PublicMediaStorage(),
        upload_to=training_file_directory_path,
        blank=True,
        max_length=512,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField()

    def __str__(self):
        return self.name

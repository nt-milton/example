from django.db import models
from tinymce.models import HTMLField


class ImplementationGuideBlueprint(models.Model):
    class Meta:
        verbose_name_plural = 'Implementation Guides Blueprint'

    name = models.CharField(unique=True, max_length=255)
    airtable_record_id = models.CharField(blank=True, max_length=512)
    description = HTMLField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

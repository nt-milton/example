from django.db import models


class TagBlueprint(models.Model):
    class Meta:
        verbose_name_plural = 'Tags Blueprint'

    name = models.CharField(unique=True, max_length=512)
    airtable_record_id = models.CharField(blank=True, max_length=512)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField()

    def __str__(self):
        return self.name

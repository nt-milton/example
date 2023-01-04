from django.db import models


class ChecklistBlueprint(models.Model):
    class Meta:
        verbose_name_plural = 'Checklist Blueprint'

    reference_id = models.CharField(max_length=100)
    checklist = models.TextField(max_length=200)
    airtable_record_id = models.CharField(blank=True, max_length=512)
    type = models.CharField(max_length=200)
    category = models.CharField(max_length=200)
    description = models.CharField(max_length=2048)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField()

    def __str__(self):
        return self.description

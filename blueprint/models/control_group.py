from django.db import models


class ControlGroupBlueprint(models.Model):
    class Meta:
        verbose_name_plural = 'Groups Blueprint'

    name = models.TextField(max_length=200)
    reference_id = models.CharField(max_length=50)
    airtable_record_id = models.CharField(blank=True, max_length=512)
    sort_order = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField()

    def __str__(self):
        return self.name

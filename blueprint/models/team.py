from django.db import models


class TeamBlueprint(models.Model):
    class Meta:
        verbose_name_plural = 'Teams Blueprint'

    name = models.TextField(unique=True, max_length=200)
    airtable_record_id = models.CharField(blank=True, max_length=512)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField()

    # Blank Fields
    description = models.CharField(max_length=2048, blank=True)
    charter = models.TextField(blank=True)

    def __str__(self):
        return self.name

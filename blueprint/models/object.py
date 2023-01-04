from django.db import models


class ObjectBlueprint(models.Model):
    class Meta:
        verbose_name_plural = 'Object Types Blueprint'

    display_name = models.CharField(unique=True, max_length=100)
    airtable_record_id = models.CharField(blank=True, max_length=512)
    type_name = models.CharField(max_length=100)
    color = models.CharField(max_length=100)
    icon_name = models.CharField(max_length=100)
    display_index = models.IntegerField()
    is_system_type = models.BooleanField(default=False)
    description = models.CharField(max_length=500, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField()

    def __str__(self):
        return self.display_name

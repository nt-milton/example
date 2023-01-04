from django.db import models


class ObjectAttributeBlueprint(models.Model):
    class Meta:
        verbose_name_plural = 'Object Type Attributes Blueprint'

    reference_id = models.CharField(null=True, max_length=50)
    name = models.CharField(max_length=100)
    object_type_name = models.CharField(max_length=100)
    airtable_record_id = models.CharField(blank=True, max_length=512)
    display_index = models.IntegerField()
    attribute_type = models.CharField(max_length=100)
    min_width = models.IntegerField()
    is_protected = models.BooleanField(default=False)
    default_value = models.CharField(blank=True, max_length=200)
    select_options = models.CharField(blank=True, max_length=512)
    is_required = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField()

    def __str__(self):
        return self.name

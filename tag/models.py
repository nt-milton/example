from django.db import models

from laika.constants import ATTRIBUTES_TYPE
from organization.models import Organization

TAGS_ATTRIBUTES = {'name': ATTRIBUTES_TYPE['TEXT']}


class Tag(models.Model):
    name = models.CharField(max_length=512)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='tags'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_manual = models.BooleanField(default=False)

    @classmethod
    def get_attribute_type_by_name(cls, name):
        return TAGS_ATTRIBUTES[name]

    class Meta:
        verbose_name_plural = 'tags'
        unique_together = (('name', 'organization'),)
        indexes = [
            models.Index(fields=['name', 'organization']),
        ]

    def __str__(self):
        return self.name

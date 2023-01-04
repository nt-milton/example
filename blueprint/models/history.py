from django.db import models

from organization.models import Organization

USER_MODEL = 'user.User'


class BlueprintHistory(models.Model):
    class Meta:
        verbose_name_plural = 'Blueprint History'

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='blueprint_history'
    )
    created_by = models.ForeignKey(
        USER_MODEL,
        related_name='blueprint_history',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
    )
    upload_action = models.TextField(max_length=200)
    content_description = models.TextField(max_length=2048)
    status = models.TextField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)

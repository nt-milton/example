from django.db import models

from audit.models import AuditFirm
from organization.models import Organization


class Flag(models.Model):
    class Meta:
        unique_together = (('name', 'organization'),)

    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    name = models.CharField(max_length=255)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='feature_flags'
    )
    is_enabled = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    @staticmethod
    def is_flag_enabled_for_organization(
        organization: Organization, flag_name: str
    ) -> bool:
        return Flag.objects.filter(
            name=flag_name, organization=organization, is_enabled=True
        ).exists()


class AuditorFlag(models.Model):
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    name = models.CharField(max_length=255)
    audit_firm = models.ForeignKey(
        AuditFirm,
        on_delete=models.CASCADE,
        related_name='feature_flags',
        null=True,
        blank=True,
    )
    is_enabled = models.BooleanField(default=False)

    def __str__(self):
        return self.name

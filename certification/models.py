import logging
from multiprocessing.pool import ThreadPool

from django.db import models

from laika.storage import PublicMediaStorage
from organization.models import Organization
from program.utils.hadle_cache import trigger_program_cache

logger = logging.getLogger(__name__)

pool = ThreadPool()


def certification_logo_directory_path(instance, filename):
    return f'certifications/{instance.name}/{filename}'


class Certification(models.Model):
    class Meta:
        permissions = [
            ('view_certification_readiness', 'Can view certification readiness'),
        ]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(unique=True, max_length=255)
    airtable_record_id = models.CharField(blank=True, null=True, max_length=512)
    logo = models.FileField(
        storage=PublicMediaStorage(),
        max_length=1024,
        upload_to=certification_logo_directory_path,
        blank=True,
    )
    code = models.CharField(max_length=100)
    is_visible = models.BooleanField(verbose_name='Visible in Polaris', default=False)
    sort_index = models.IntegerField(default=9999999, null=True, blank=True)
    description = models.TextField(blank=True)
    regex = models.CharField(max_length=255, blank=True)
    # Field needed to set a hardcoded value for locked certifications
    # And required to calculate locked certifications readiness
    required_action_items = models.IntegerField(default=0)

    def __str__(self):
        return self.name


class CertificationSection(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=100)
    airtable_record_id = models.CharField(blank=True, null=True, max_length=512)
    certification = models.ForeignKey(
        Certification, on_delete=models.CASCADE, related_name='sections'
    )

    class Meta:
        unique_together = (
            'name',
            'certification',
        )

    def __str__(self):
        return self.name


class UnlockedOrganizationCertification(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='unlocked_certifications'
    )

    certification = models.ForeignKey(
        Certification, on_delete=models.CASCADE, related_name='unlocked_organizations'
    )
    target_audit_start_date = models.DateTimeField(null=True, blank=True)
    target_audit_completion_date = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self._state.adding and not kwargs.get('no_cache'):
            super(UnlockedOrganizationCertification, self).save()
            logger.info(
                f'Must update playbooks cache for organization: {self.organization.id}'
            )
            trigger_program_cache.delay(self.organization.id)
        else:
            super(UnlockedOrganizationCertification, self).save()

    class Meta:
        verbose_name_plural = 'certifications'

    def __str__(self):
        return self.certification.name


class ArchivedUnlockedOrganizationCertification(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='archived_unlocked_certifications',
    )

    certification = models.ForeignKey(
        Certification,
        on_delete=models.CASCADE,
        related_name='archived_unlocked_organizations',
    )
    target_audit_start_date = models.DateTimeField(null=True, blank=True)
    target_audit_completion_date = models.DateTimeField(null=True, blank=True)

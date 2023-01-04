import logging

from django.db.models import Q
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from evidence.related_models import EVIDENCE_MODELS
from evidence.utils import delete_evidence_check
from vendor.models import (
    DISCOVERY_STATUS_CONFIRMED,
    DISCOVERY_STATUS_IGNORED,
    DISCOVERY_STATUS_NEW,
    DISCOVERY_STATUS_PENDING,
    OrganizationVendor,
    OrganizationVendorEvidence,
    Vendor,
    VendorCandidate,
)

logger = logging.getLogger('vendor_evidence')


@receiver(post_delete, sender=OrganizationVendorEvidence)
def execute_post_delete_vendor_evidence_actions(sender, instance, **kwargs):
    if instance and instance.evidence:
        logger.info(f'Deleting organization vendor evidence: {instance.evidence.id}')
        organization = instance.organization_vendor.organization
        delete_evidence_check(organization, instance.evidence, EVIDENCE_MODELS)


@receiver(post_save, sender=Vendor)
def match_new_vendor_candidates_by_vendor_name(sender, instance, **kwargs):
    VendorCandidate.objects.filter(
        Q(status=DISCOVERY_STATUS_PENDING) | Q(vendor__isnull=True), name=instance.name
    ).update(vendor=instance, status=DISCOVERY_STATUS_NEW)


@receiver(post_save, sender=VendorCandidate)
def match_new_vendor_candidates_by_vendor_alias(sender, instance, **kwargs):
    if instance.vendor:
        VendorCandidate.objects.filter(
            Q(status=DISCOVERY_STATUS_PENDING) | Q(vendor__isnull=True),
            name=instance.name,
        ).update(vendor=instance.vendor, status=DISCOVERY_STATUS_NEW)


@receiver(post_save, sender=OrganizationVendor)
def update_vendor_candidate_if_relation_is_created(sender, instance, **kwargs):
    VendorCandidate.objects.filter(
        vendor=instance.vendor, organization=instance.organization
    ).update(status=DISCOVERY_STATUS_CONFIRMED)


@receiver(post_delete, sender=OrganizationVendor)
def update_vendor_candidate_if_relation_is_removed(sender, instance, **kwargs):
    VendorCandidate.objects.filter(
        vendor=instance.vendor, organization=instance.organization
    ).update(status=DISCOVERY_STATUS_IGNORED)

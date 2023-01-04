import logging

from django.db.models.signals import post_delete
from django.dispatch import receiver

from drive.models import DriveEvidence
from evidence.related_models import EVIDENCE_MODELS
from evidence.utils import delete_evidence_check

logger = logging.getLogger('drive_evidence_signal')


@receiver(post_delete, sender=DriveEvidence)
def execute_post_delete_drive_evidence_actions(sender, instance, **kwargs):
    if instance and instance.evidence:
        logger.info(f'Deleting drive evidence: {instance.evidence.id}')
        organization = instance.drive.organization
        delete_evidence_check(organization, instance.evidence, EVIDENCE_MODELS)

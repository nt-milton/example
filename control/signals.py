import logging

from django.db.models.signals import post_delete
from django.dispatch import receiver

from control.models import ControlEvidence
from evidence.related_models import EVIDENCE_MODELS
from evidence.utils import delete_evidence_check

logger = logging.getLogger('control_evidence')


@receiver(post_delete, sender=ControlEvidence)
def execute_post_delete_control_evidence_actions(sender, instance, **kwargs):
    if instance and instance.evidence:
        logger.info(f'Deleting control evidence: {instance.evidence.id}')
        organization = instance.organization_vendor.organization
        delete_evidence_check(organization, instance.evidence, EVIDENCE_MODELS)

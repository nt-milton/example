import logging

from django.db.models.signals import post_delete
from django.dispatch import receiver

from dataroom.models import DataroomEvidence
from evidence.related_models import EVIDENCE_MODELS
from evidence.utils import delete_evidence_check

logger = logging.getLogger('dataroom_evidence')


@receiver(post_delete, sender=DataroomEvidence)
def execute_post_delete_dr_evidence_actions(sender, instance, **kwargs):
    if instance and instance.evidence:
        logger.info(f'Deleting dataroom evidence: {instance.evidence.id}')
        organization = instance.dataroom.organization
        delete_evidence_check(organization, instance.evidence, EVIDENCE_MODELS)

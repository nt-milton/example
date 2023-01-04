import logging
from multiprocessing.pool import ThreadPool

from django.db.models.signals import post_save
from django.dispatch import receiver

from .admin import FieldworkSeed
from .constants import IN_PROGRESS
from .tasks import seed_audit_fieldwork

logger = logging.getLogger('seeder')
pool = ThreadPool()


@receiver(post_save, sender=FieldworkSeed, dispatch_uid="post_save_seed")
def import_fieldwork_seed_file(sender, instance, created, **kwargs):
    if instance.organization:
        return
    if created:
        instance.status = IN_PROGRESS
        instance.save()

        seed_audit_fieldwork(instance)

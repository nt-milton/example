from multiprocessing.pool import ThreadPool

from django.db.models.signals import post_save
from django.dispatch import receiver
from log_request_id import local

from laika.celery import MAX_PRIORITY

from .constants import SETUP_COMPLETE, SYNC
from .models import ConnectionAccount
from .tasks import run_and_notify_connection, run_initial_and_notify_monitors

pool = ThreadPool()


@receiver(post_save, sender=ConnectionAccount)
def run_integration(sender, instance, **kwargs):
    if instance.status == SETUP_COMPLETE:
        instance.status = SYNC
        instance.save()
        celery_execution = instance.integration.metadata.get('celery_execution', False)
        if celery_execution:
            run_initial_and_notify_monitors.apply_async(
                args=[instance.id], countdown=1, priority=MAX_PRIORITY
            )
        else:
            pool.apply_async(
                run_and_notify_connection, args=(instance, local.request_id)
            )

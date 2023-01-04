import logging

from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from search.cloudsearch import is_cloudsearch_enabled
from search.indexing.policy_index import policy_search_index

from .models import Policy

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Policy, dispatch_uid='add_policy_to_index')
def add_to_index(sender, instance, **kwargs):
    if not is_cloudsearch_enabled:
        return
    old_instance = Policy.objects.filter(id=instance.id).first()
    if (
        old_instance
        and old_instance.name == instance.name
        and old_instance.description == instance.description
        and old_instance.policy_text == instance.policy_text
        and old_instance.is_published == instance.is_published
    ):
        return
    policy_search_index.index_record(instance)


@receiver(post_delete, sender=Policy, dispatch_uid='remove_policy_from_index')
def remove_from_index(sender, instance, **kwargs):
    if not is_cloudsearch_enabled:
        return
    policy_search_index.remove_index_records_async(
        record_ids=[instance.id], resource_type=policy_search_index.RESOURCE_TYPE
    )

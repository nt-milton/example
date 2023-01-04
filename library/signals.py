from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver

from library.models import Question, Questionnaire
from search.cloudsearch import is_cloudsearch_enabled
from search.indexing.question_index import question_search_index


@receiver(pre_delete)
def delete_question(sender, instance, **kwargs):
    if sender == Question:
        instance.reconcile_equivalent_questions()


@receiver(post_delete, sender=Question, dispatch_uid='remove_question_from_index')
def remove_from_index(sender, instance, **kwargs):
    if not is_cloudsearch_enabled:
        return
    question_search_index.remove_index_records_async(
        record_ids=[instance.id], resource_type=question_search_index.RESOURCE_TYPE
    )


@receiver(pre_delete)
def delete_questionnaire(sender, instance, **kwargs):
    if sender == Questionnaire and instance.dataroom:
        instance.dataroom.is_soft_deleted = True
        instance.dataroom.save()

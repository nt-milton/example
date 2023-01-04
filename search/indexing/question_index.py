import logging

from django.db.models import Q

from library.models import Question
from search.indexing.base_index import BaseIndex
from search.indexing.types import IndexRecord

logger = logging.getLogger(__name__)


class QuestionSearchIndex(BaseIndex):
    CHUNK_SIZE = 1000
    RESOURCE_TYPE = 'question'

    def get_is_published(self, question):
        return Question.objects.filter(
            Q(Q(questionnaires__isnull=True) | Q(questionnaires__completed=True)),
            id=question.id,
        ).exists()

    def mapper(self, question, **kwargs):
        if kwargs.get('fetch_publish', True):
            is_published = self.get_is_published(question)
        else:
            is_published = kwargs.get('published')

        return IndexRecord(
            resource_id=question.id,
            resource_type=self.RESOURCE_TYPE,
            organization_id=question.library_entry.organization_id,
            title=question.text,
            main_content=question.library_entry.answer_text,
            secondary_content=question.library_entry.short_answer_text,
            category=[],
            is_draft=not is_published,
        )

    def get_new_index_records_queryset(self, indexed_records):
        return Question.objects.exclude(id__in=indexed_records).prefetch_related(
            'library_entry'
        )

    def get_updated_index_records(self, from_date):
        return Question.objects.filter(updated_at__gt=from_date).prefetch_related(
            'library_entry'
        )

    def get_deleted_index_records(self, indexed_records):
        question_ids = Question.objects.all().values_list('id', flat=True)
        return indexed_records.exclude(
            key__in=[str(question_id) for question_id in question_ids]
        )

    def add_to_index(self, questions, fetch_publish=True, published=False):
        BaseIndex.add_index_records_async(
            records=[
                self.mapper(question, fetch_publish=fetch_publish, published=published)
                for question in questions
            ],
            resource_type=self.RESOURCE_TYPE,
        )


question_search_index = QuestionSearchIndex()

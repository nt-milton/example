import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from multiprocessing.pool import ThreadPool
from typing import Any, List

from django.db.models.signals import post_delete
from django.dispatch import receiver

from search.cloudsearch import add_index_records, remove_index_records
from search.indexing.types import IndexRecord
from search.models import Index
from search.utils import batch_iterator

logger = logging.getLogger(__name__)
pool = ThreadPool()


class BaseIndex(ABC):
    CHUNK_SIZE = 0
    RESOURCE_TYPE = ''

    @abstractmethod
    def mapper(self, record: Any):
        pass

    @abstractmethod
    def get_new_index_records_queryset(self, indexed_records: List[Any]):
        pass

    @abstractmethod
    def get_updated_index_records(self, from_date):
        pass

    @abstractmethod
    def get_deleted_index_records(self, indexed_records):
        pass

    @staticmethod
    def get_indexed_records(resource_type: str):
        return Index.objects.filter(type=resource_type)

    @staticmethod
    def get_indexed_record_ids(resource_type: str):
        indexed_records = BaseIndex.get_indexed_records(resource_type).values_list(
            'key', flat=True
        )
        return list(indexed_records)

    @staticmethod
    def add_index_records_async(*, records: List[IndexRecord], resource_type: str):
        pool.apply_async(
            add_index_records,
            args=(records, resource_type),
        )

    @staticmethod
    def add_index_records(*, records: List[IndexRecord], resource_type: str):
        add_index_records(records, resource_type)

    @staticmethod
    def remove_index_records_async(*, record_ids: List[Any], resource_type: str):
        pool.apply_async(remove_index_records, args=(record_ids, resource_type))

    @staticmethod
    def remove_index_records(*, record_ids: List[Any], resource_type: str):
        remove_index_records(record_ids, resource_type)

    def register_remove_record_signal(self, model):
        @receiver(
            post_delete,
            sender=model,
            dispatch_uid=f'remove_${self.RESOURCE_TYPE}_from_index',
        )
        def remove_from_index(sender, instance, **kwargs):
            BaseIndex.remove_index_records_async(
                record_ids=[instance.id], resource_type=self.RESOURCE_TYPE
            )

    def index_records_from_qs(self, qs):
        for records, completed in batch_iterator(qs, chunk_size=self.CHUNK_SIZE):
            BaseIndex.add_index_records(
                records=[self.mapper(record) for record in records],
                resource_type=self.RESOURCE_TYPE,
            )

    def _reconcile_records_to_add(self):
        last_day = datetime.today() - timedelta(days=1)
        indexed_record_ids = BaseIndex.get_indexed_record_ids(self.RESOURCE_TYPE)
        new_records = self.get_new_index_records_queryset(indexed_record_ids)
        updated_records = self.get_updated_index_records(last_day)
        qs = new_records.union(updated_records)
        self.index_records_from_qs(qs)

    def _reconcile_records_to_delete(self):
        record_ids_to_delete = self.get_deleted_index_records(
            indexed_records=BaseIndex.get_indexed_records(self.RESOURCE_TYPE)
        ).values_list('key', flat=True)
        BaseIndex.remove_index_records(
            record_ids=record_ids_to_delete, resource_type=self.RESOURCE_TYPE
        )

    def reconcile(self):
        self._reconcile_records_to_add()
        self._reconcile_records_to_delete()

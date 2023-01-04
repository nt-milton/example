import logging

from policy.models import Policy
from search.indexing.base_index import BaseIndex
from search.indexing.types import IndexRecord

logger = logging.getLogger(__name__)


class PolicySearchIndex(BaseIndex):
    CHUNK_SIZE = 5
    RESOURCE_TYPE = 'policy'

    def mapper(self, policy):
        return IndexRecord(
            resource_id=policy.id,
            resource_type=self.RESOURCE_TYPE,
            organization_id=policy.organization_id,
            title=policy.name,
            main_content=policy.policy_text,
            secondary_content=policy.description,
            category=[policy.category],
            is_draft=not policy.is_published,
        )

    def get_new_index_records_queryset(self, indexed_policies):
        return Policy.objects.all().exclude(id__in=indexed_policies)

    def get_updated_index_records(self, from_date):
        return Policy.objects.filter(updated_at__gt=from_date)

    def get_deleted_index_records(self, indexed_records):
        policy_ids = Policy.objects.all().values_list('id', flat=True)
        return indexed_records.exclude(
            key__in=[str(policy_id) for policy_id in policy_ids]
        )

    def index_record(self, record):
        BaseIndex.add_index_records_async(
            records=[self.mapper(record)], resource_type=self.RESOURCE_TYPE
        )


policy_search_index = PolicySearchIndex()

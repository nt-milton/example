import logging

import graphene

from laika.decorators import concierge_service
from organization.salesforce.tasks import sync_salesforce_organizations_with_polaris

logger = logging.getLogger(__name__)


class SyncSalesforceData(graphene.Mutation):
    success = graphene.Boolean()

    @concierge_service(
        permission='user.view_concierge',
        exception_msg='Failed to sync data with Salesforce. Please try again.',
        revision_name='Sync data from Salesforce To Polaris',
    )
    def mutate(self, info):
        user = info.context.user
        logger.info(f'Synchronizing Organizations from Salesforce by: {user}')
        async_task_result: dict = sync_salesforce_organizations_with_polaris()

        return SyncSalesforceData(success=async_task_result.get('success'))

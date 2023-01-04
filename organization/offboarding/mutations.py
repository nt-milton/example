import logging
from datetime import datetime
from multiprocessing.pool import ThreadPool

import graphene
import pytz

from integration.factory import get_integration
from integration.models import ConnectionAccount, Integration
from laika.decorators import laika_service
from laika.utils.websocket import send_ws_message_to_group
from organization.models import OrganizationChecklist, OrganizationChecklistRun
from user.utils.user_model_query import find_user_by_id_type
from vendor.models import Vendor

pool = ThreadPool()
logger = logging.getLogger(__name__)


class RunAccessScan(graphene.Mutation):
    class Arguments:
        user_id = graphene.String(required=True)
        vendor_ids = graphene.List(graphene.String)

    success = graphene.Boolean()

    @laika_service(
        permission='organization.change_organizationchecklist',
        exception_msg='Failed to run access scan',
    )
    def mutate(self, info, **kwargs):
        organization = info.context.user.organization
        checklist = OrganizationChecklist.objects.get(
            action_item__name='Offboarding', organization=organization
        )
        owner = find_user_by_id_type(kwargs.get('user_id'), info)
        checklist_run = OrganizationChecklistRun.objects.get(
            owner=owner, checklist=checklist
        )
        connection_accounts = ConnectionAccount.objects.filter(
            laika_objects__object_type__type_name='user',
            laika_objects__data__Email=owner.email,
            integration__vendor__id__in=kwargs.get('vendor_ids'),
            organization=organization,
        ).distinct()
        checklist_run.metadata['runningScan'] = True
        now = datetime.now(pytz.utc)
        checklist_run.metadata['runningStart'] = int(datetime.timestamp(now))
        checklist_run.metadata['vendorIds'] = [
            connection_account.integration.vendor.id
            for connection_account in connection_accounts
        ]
        checklist_run.save()
        pool.apply_async(
            run_access_scan, args=(info, connection_accounts, checklist_run)
        )

        return RunAccessScan(success=True)


def run_access_scan(info, connection_accounts: list[ConnectionAccount], checklist_run):
    for connection_account in connection_accounts:
        try:
            integration = get_integration(connection_account)
            integration.run(connection_account)
        except Exception as e:
            logger.error(
                'Failed to run integration, connection account'
                f'id: {connection_account.id} error: {e}'
            )
    checklist_run.metadata = {
        **checklist_run.metadata,
        'runningScan': False,
        'runningStart': None,
        'vendorIds': [],
    }
    checklist_run.save()

    email = checklist_run.owner.email
    organization = info.context.user.organization

    integration_ids = Integration.objects.filter(
        connection_accounts__laika_objects__data__Email=email,
        connection_accounts__laika_objects__deleted_at__isnull=True,
        connection_accounts__organization=organization,
    ).values_list('id', flat=True)

    pending_vendors_count = (
        Vendor.objects.filter(integration__id__in=integration_ids).distinct().count()
    )

    send_ws_message_to_group(
        room_id=info.context.user.organization.id,
        sender=info.context.user.email,
        receiver=info.context.user.email,
        logger=logger,
        event_type='OFFBOARDING_SCAN_COMPLETED',
        payload={
            'pendingVendorsCount': pending_vendors_count,
            'user': {
                'id': checklist_run.owner.id,
                'firsName': checklist_run.owner.first_name,
                'lastName': checklist_run.owner.last_name,
            },
        },
    )

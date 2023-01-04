import logging
from multiprocessing.pool import ThreadPool
from typing import Optional

from django.db.models import Q

from laika.celery import app as celery_app
from organization.models import DEACTIVATED, Organization
from organization.salesforce.constants import ID_SALESFORCE_FIELD
from organization.salesforce.implementation import update_or_create_organization
from organization.salesforce.salesforce_rest_client import (
    get_access_token,
    get_salesforce_organizations_ready_to_sync,
    update_polaris_id_in_synced_orgs,
    update_salesforce_organization,
)
from organization.salesforce.salesforce_types import SalesforceAccountType
from organization.salesforce.utils import salesforce_account_adapter
from organization.slack_post_message import post_error_message

logger = logging.getLogger(__name__)
pool = ThreadPool()


@celery_app.task(
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2},
    retry_backoff=True,
    name='Sync Salesforce Data',
)
def sync_salesforce_organizations_with_polaris():
    new_orgs = []
    status_detail = []
    try:
        sf_organizations = get_organizations_to_sync_from_salesforce()
        for organization in sf_organizations:
            synced_organization, error_detail = update_or_create_organization(
                organization
            )
            if synced_organization:
                logger.info(f'Org {synced_organization.name} synced with SFDC')
                if organization.get('Polaris_ID__c') is None:
                    new_orgs.append(organization.get(ID_SALESFORCE_FIELD))
            for error in error_detail:
                logger.warning(f'sync_error_detail: {error}')
                status_detail.append(error)
    except Exception as e:
        logger.warning(f'Error sync organization from Salesforce: {e}')
        return {'success': False}

    if status_detail:
        post_error_message('\n\n'.join(status_detail))

    try:
        if new_orgs:
            update_polaris_id_to_new_synced_orgs(new_orgs)
    except Exception as e:
        logger.warning(f'Error sending data to Salesforce: {e}')

    logger.info('Sync process has finished successfully')
    return {'success': True}


def get_laika_valid_organizations_to_sync() -> list[str]:
    return list(
        Organization.objects.filter(~Q(state=DEACTIVATED))
        .filter(~Q(sfdc_id=None) | ~Q(sfdc_id=''))
        .distinct()
        .values_list('sfdc_id', flat=True)
    )


def get_organizations_to_sync_from_salesforce() -> Optional[dict]:
    try:
        authentication_values = get_access_token()
        if authentication_values:
            sfdc_ids_list = get_laika_valid_organizations_to_sync()
            return get_salesforce_organizations_ready_to_sync(
                authentication_values, sfdc_ids_list
            )
    except Exception as e:
        message = f'Error trying to get orgs from Laika to sync with SF: {e}'
        logger.warning(message)
    return None


@celery_app.task(
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2},
    retry_backoff=True,
    name='Push org data to Salesforce',
)
def update_organization_in_salesforce(organization_id: str):
    organization = Organization.objects.get(id=organization_id)
    payload: SalesforceAccountType = salesforce_account_adapter(organization)
    sfdc_id = organization.sfdc_id
    try:
        authentication_values = get_access_token()
        if authentication_values and sfdc_id:
            logger.info(f'Updating: {organization.name} to SF')
            update_salesforce_organization(authentication_values, sfdc_id, payload)
    except Exception as e:
        message = f'Error trying to update organization data to SFDC: {e}'
        org_name = organization.name
        post_error_message(f'{org_name} org was not updated in Salesforce.')
        logger.warning(message)
    return None


def get_laika_recent_synced_organizations(orgs: Optional[list]) -> Optional[list]:
    return [
        {"polarisID": str(organization.id), "salesforceID": organization.sfdc_id}
        for organization in Organization.objects.filter(sfdc_id__in=orgs).distinct()
    ]


def update_polaris_id_to_new_synced_orgs(orgs: Optional[list[str]]):
    if not orgs:
        return

    try:
        orgs_to_update = get_laika_recent_synced_organizations(orgs)
        authentication_values = get_access_token()
        if authentication_values and orgs_to_update:
            update_polaris_id_in_synced_orgs(authentication_values, orgs_to_update)
    except Exception as e:
        message = f'Error trying to update Polaris ID to SF: {e}'
        logger.warning(message)

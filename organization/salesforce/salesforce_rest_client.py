import http
import json
import logging
from typing import Optional

import requests

from organization.salesforce.constants import (
    INTEGRATION_SALESFORCE_AUTH_URL,
    INTEGRATION_SALESFORCE_CLIENT_ID,
    INTEGRATION_SALESFORCE_CONSUMER_SECRET,
    SALESFORCE_API_USER,
    SALESFORCE_API_USER_PASSWORD,
    SALESFORCE_POLARIS_ENDPOINT_URL,
    SALESFORCE_STATES,
    SALESFORCE_USER_URL_API,
)
from organization.salesforce.salesforce_types import SalesforceAccountType

logger_name = __name__
logger = logging.getLogger(logger_name)


def get_access_token() -> Optional[dict]:
    try:
        response = requests.post(
            INTEGRATION_SALESFORCE_AUTH_URL,
            data={
                'client_id': INTEGRATION_SALESFORCE_CLIENT_ID,
                'client_secret': INTEGRATION_SALESFORCE_CONSUMER_SECRET,
                'grant_type': 'password',
                'username': SALESFORCE_API_USER,
                'password': SALESFORCE_API_USER_PASSWORD,
            },
        )
        if response.status_code != http.HTTPStatus.NO_CONTENT and response.headers[
            "content-type"
        ].strip().startswith("application/json"):
            json_res = response.json()
            access_token = json_res['access_token']
            auth = {'Authorization': 'Bearer ' + access_token}
            instance_url = json_res['instance_url']
            return dict(auth=auth, instance_url=instance_url)
        return None
    except requests.RequestException as e:
        logger.error(f'Error getting access token from Salesforce: {e}')
        return None
    except Exception as ex:
        logger.error(f'Error getting access token from Salesforce: {ex}')
        return None


def get_user_details(user: str, authentication_values: dict):
    instance_url = authentication_values.get('instance_url')
    if instance_url:
        url = instance_url + SALESFORCE_USER_URL_API + user
        res = requests.get(url, headers=authentication_values.get('auth'))
        if res.status_code == http.HTTPStatus.NOT_FOUND:
            return None
        return res.json()


def get_all_salesforce_organizations(authentication_values: dict):
    instance_url = authentication_values.get('instance_url')
    if instance_url:
        url = (
            instance_url
            + '/services/data/v55.0/query/?q=SELECT+Account_ID_18_char__c,'
            + 'name,Compliance_Architect__c,Customer_Success_Manager__c+'
            + 'from+Account+where+Account_ID_18_char__c!=null'
        )
        res = requests.get(url, headers=authentication_values.get('auth'))
        return res.json()


def get_salesforce_organizations_ready_to_sync(
    authentication_values: dict, sfdc_ids_list: list[str]
):
    instance_url = authentication_values.get('instance_url')
    if instance_url:
        url = instance_url + SALESFORCE_POLARIS_ENDPOINT_URL
        payload = {
            'polarisAccounts': ','.join(sfdc_ids_list),
            'polarisStates': ','.join(SALESFORCE_STATES),
        }
        res = requests.get(
            url, headers=authentication_values.get('auth'), params=payload
        )
        return res.json()


def update_salesforce_organization(
    authentication_values: dict, sfdc_id: str, payload: SalesforceAccountType
):
    instance_url = authentication_values.get('instance_url')
    auth = authentication_values.get('auth')
    logger.info(f'payload:  {json.dumps(payload)}')

    if instance_url and sfdc_id and auth:
        auth['Content-Type'] = 'application/json'
        url = instance_url + SALESFORCE_POLARIS_ENDPOINT_URL + f'/{sfdc_id}'
        res = requests.put(
            url,
            headers=auth,
            data=json.dumps(payload),
        )
        logger.info(f'Response from PUT method in REST API from Salesforce: {res}')
        return res.json()


def update_polaris_id_in_synced_orgs(authentication_values: dict, orgs_to_update: list):
    instance_url = authentication_values.get('instance_url')
    auth = authentication_values.get('auth')

    if instance_url and auth:
        auth['Content-Type'] = 'application/json'
        url = instance_url + SALESFORCE_POLARIS_ENDPOINT_URL
        payload = {'accs': orgs_to_update}
        res = requests.post(url, headers=auth, data=json.dumps(payload))
        logger.info(f'Response from POST method in REST API from Salesforce: {res}')
        return res.status_code

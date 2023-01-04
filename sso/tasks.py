import json
import logging

import requests

from laika.celery import app as celery_app
from laika.okta.api import OktaApi
from sso.constants import (
    AZURE,
    GOOGLE,
    OKTA,
    OKTA_HEADERS,
    OKTA_INSTANCE_URL,
    OKTA_MAPPINGS_API,
    OKTA_USERS_API,
    get_okta_properties_url,
)
from sso.okta.request_bodies import (
    AZURE_PROPERTIES,
    OKTA_OR_GOOGLE_PROPERTIES,
    OKTA_TO_AZURE_MAPPINGS,
    OKTA_TO_OKTA_OR_GOOGLE_CLIENT_MAPPINGS,
    get_azure_to_okta_mappings,
    get_client_okta_to_okta_mappings,
    get_google_to_okta_mappings,
)

logger = logging.getLogger('sso')


def generate_okta_request_bodies(provider, organization_name, organization_id):
    if provider == AZURE:
        properties = AZURE_PROPERTIES
        provider_to_okta_mappings = get_azure_to_okta_mappings(
            organization_name, organization_id
        )
        okta_to_provider_mappings = OKTA_TO_AZURE_MAPPINGS
    elif provider == OKTA:
        properties = OKTA_OR_GOOGLE_PROPERTIES
        provider_to_okta_mappings = get_client_okta_to_okta_mappings(
            organization_name, organization_id
        )
        okta_to_provider_mappings = OKTA_TO_OKTA_OR_GOOGLE_CLIENT_MAPPINGS
    elif provider == GOOGLE:
        properties = OKTA_OR_GOOGLE_PROPERTIES
        provider_to_okta_mappings = get_google_to_okta_mappings(
            organization_name, organization_id
        )
        okta_to_provider_mappings = OKTA_TO_OKTA_OR_GOOGLE_CLIENT_MAPPINGS
    else:
        return None
    return {
        'properties': properties,
        'provider_to_okta_mappings': provider_to_okta_mappings,
        'okta_to_provider_mappings': okta_to_provider_mappings,
    }


def okta_post(url, data):
    requests.post(url, headers=OKTA_HEADERS, data=json.dumps(data))


def delete_inactive_okta_users(org_id: str):
    params = {
        'search': f'''profile.organizationId eq "{org_id}"'''
        '''and status eq "PASSWORD_EXPIRED"'''
    }
    response = requests.get(
        f'{OKTA_INSTANCE_URL}/{OKTA_USERS_API}', params=params, headers=OKTA_HEADERS
    )
    users = response.json()
    for user in users:
        OktaApi.delete_user(user['id'])


@celery_app.task(name='Setup Okta Mappings')
def setup_okta_mappings(idp_id, organization_id, organization_name, provider):
    source_url = f'{OKTA_INSTANCE_URL}/{OKTA_MAPPINGS_API}?sourceId={idp_id}'
    target_url = f'{OKTA_INSTANCE_URL}/{OKTA_MAPPINGS_API}?target={idp_id}'
    properties_url = f'{OKTA_INSTANCE_URL}/{get_okta_properties_url(idp_id)}'
    try:
        source_response = requests.get(source_url, headers=OKTA_HEADERS)
        source = source_response.json()
        target_response = requests.get(target_url, headers=OKTA_HEADERS)
        target = target_response.json()
        source_mapping_id = source[0]['id']
        target_mapping_id = target[0]['id']
        post_source_url = f'{OKTA_INSTANCE_URL}/{OKTA_MAPPINGS_API}/{source_mapping_id}'
        post_target_url = f'{OKTA_INSTANCE_URL}/{OKTA_MAPPINGS_API}/{target_mapping_id}'
        request_bodies = generate_okta_request_bodies(
            provider, organization_name, organization_id
        )
        okta_post(properties_url, request_bodies['properties'])
        okta_post(post_source_url, request_bodies['provider_to_okta_mappings'])
        okta_post(post_target_url, request_bodies['okta_to_provider_mappings'])
    except requests.RequestException as e:
        logger.error(
            'SSO - Error creating Okta mappings'
            f' organization: {organization_id}'
            f' provider: {provider}'
            f' error: {e}'
        )
        return None


@celery_app.task(name='Delete inactive Okta users')
def delete_inactive_okta_users_task(org_id: str):
    delete_inactive_okta_users(org_id)

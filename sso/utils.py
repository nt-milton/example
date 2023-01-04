import datetime
import logging
import math
import re

import requests

from feature.constants import okta_feature_flag, sso_feature_flag
from feature.models import Flag
from laika.utils.exceptions import ServiceException
from sso.constants import (
    DONE_ENABLED,
    EXISTING_KEY_ERROR_CODE,
    OKTA_HEADERS,
    OKTA_IDPS_API,
    OKTA_INSTANCE_URL,
    OKTA_KEYS_API,
    OKTA_RESPONSE_CREDENTIALS,
    OKTA_RESPONSE_PROTOCOL,
    OKTA_RULES_API,
)
from sso.models import IdentityProvider
from sso.okta.request_bodies import generate_request_body, generate_routing_rule_body

logger = logging.getLogger('sso')

MAX_ORG_NAME_LENGTH = 40
DELETE_IDP_ENDPOINT = OKTA_INSTANCE_URL + '/api/v1/idps/{idp_id}'


def get_okta_idp(idp_id):
    url = f'{OKTA_INSTANCE_URL}/api/v1/idps/{idp_id}'
    try:
        response = requests.get(url, headers=OKTA_HEADERS)
        return prepare_okta_response(response)
    except requests.RequestException as e:
        logger.error(f'Error creating idp in Okta: {e}')
        return None


def create_okta_idp(organization, provider):
    url = f'{OKTA_INSTANCE_URL}/{OKTA_IDPS_API}'
    data = generate_request_body(organization.name, provider)
    try:
        response = requests.post(url, headers=OKTA_HEADERS, json=data)
        return prepare_okta_response(response)
    except requests.RequestException as e:
        logger.error(f'Error creating idp in Okta: {e}')
        return None


def update_okta_idp(idp_id, data):
    url = f'{OKTA_INSTANCE_URL}/{OKTA_IDPS_API}/{idp_id}'
    try:
        response = requests.put(url, headers=OKTA_HEADERS, json=data)
        return prepare_okta_response(response)
    except requests.RequestException as e:
        logger.error(f'Error updating idp in Okta: {e}')
        return None


def get_okta_idp_certificate(key_id):
    url = f'{OKTA_INSTANCE_URL}/{OKTA_KEYS_API}/{key_id}'
    try:
        response = requests.get(url, headers=OKTA_HEADERS)
        data = response.json()
        key = data['x5c'][0]
        return key
    except requests.RequestException:
        return None


def get_cert_existing_key(new_key):
    return new_key['errorSummary'].split('=')[1].replace('.', '')


def upload_okta_idp_certificate(certificate):
    url = f'{OKTA_INSTANCE_URL}/{OKTA_KEYS_API}'
    data = {'x5c': [certificate]}
    try:
        response = requests.post(url, headers=OKTA_HEADERS, json=data)
        new_key = response.json()
        if 'errorCode' in new_key:
            if new_key['errorCode'] == EXISTING_KEY_ERROR_CODE:
                return get_cert_existing_key(new_key)
            else:
                error = 'Okta error'
                logger.error(f'Failed to upload key: {error}')
                raise ServiceException('Please provide a valid certificate')
        return new_key['kid']
    except requests.RequestException:
        raise ServiceException('An error happened connecting with provider')


def remove_header_from_certificate(cert):
    return (
        cert.replace('-----BEGIN CERTIFICATE-----', '')
        .replace('-----END CERTIFICATE-----', '')
        .replace('\n', '')
    )


domain_pattern = re.compile(
    r'^(([a-zA-Z]{1})|([a-zA-Z]{1}[a-zA-Z]{1})|'
    r'([a-zA-Z]{1}[0-9]{1})|([0-9]{1}[a-zA-Z]{1})|'
    r'([a-zA-Z0-9][-_.a-zA-Z0-9]{0,61}[a-zA-Z0-9]))\.'
    r'([a-zA-Z]{2,13}|[a-zA-Z0-9-]{2,30}.[a-zA-Z]{2,3})$'
)


def valid_domain(value):
    return domain_pattern.match(value)


def create_okta_routing_rule(organization_name, idp_id, domains):
    url = f'{OKTA_INSTANCE_URL}/{OKTA_RULES_API}'
    ts = math.trunc(datetime.datetime.now().timestamp())
    short_organization_name = f'{organization_name[0:MAX_ORG_NAME_LENGTH]}{ts}'
    data = generate_routing_rule_body(short_organization_name, idp_id, domains)
    try:
        response = requests.post(url, headers=OKTA_HEADERS, json=data)
        new_rule = response.json()
        return new_rule
    except requests.RequestException:
        return None


def delete_okta_routing_rule(rule_id):
    url = f'{OKTA_INSTANCE_URL}/{OKTA_RULES_API}/{rule_id}'
    try:
        status = requests.delete(url, headers=OKTA_HEADERS)
        return status
    except requests.RequestException:
        return None


def activate_feature_flags_on_idp_activate(organization):
    Flag.objects.update_or_create(
        name=sso_feature_flag, organization=organization, defaults={'is_enabled': True}
    )

    Flag.objects.update_or_create(
        name=okta_feature_flag, organization=organization, defaults={'is_enabled': True}
    )


def disable_feature_flags_on_idp_disable(organization):
    Flag.objects.update_or_create(
        name=sso_feature_flag, organization=organization, defaults={'is_enabled': False}
    )


def update_okta_rule(idp, domains, state):
    if state == DONE_ENABLED:
        if idp.rule_id:
            delete_okta_routing_rule(idp.rule_id)
        try:
            rule_response = create_okta_routing_rule(
                idp.organization.name, idp.idp_id, domains=domains
            )
        except requests.RequestException:
            raise ServiceException('Failed to set domains')
        if 'id' in rule_response:
            return rule_response['id']
        return None


def replace_laika_urls(okta_response):
    updated_response = okta_response
    audience = okta_response[OKTA_RESPONSE_PROTOCOL][OKTA_RESPONSE_CREDENTIALS][
        'trust'
    ]['audience']
    acs = okta_response['_links']['acs']['href']
    updated_audience = audience.replace('laika.okta.com', 'auth.heylaika.com')
    updated_acs = acs.replace('laika.okta.com', 'auth.heylaika.com')

    (
        updated_response[OKTA_RESPONSE_PROTOCOL][OKTA_RESPONSE_CREDENTIALS]['trust'][
            'audience'
        ]
    ) = updated_audience
    (updated_response['_links']['acs']['href']) = updated_acs

    return updated_response


def valid_okta_response(okta_response):
    return (
        OKTA_RESPONSE_PROTOCOL in okta_response
        and OKTA_RESPONSE_CREDENTIALS in okta_response[OKTA_RESPONSE_PROTOCOL]
    )


def prepare_okta_response(response):
    okta_response = response.json()
    if valid_okta_response(okta_response):
        return replace_laika_urls(okta_response)
    if 'errorSummary' in okta_response:
        errorSummary = okta_response['errorSummary']
        logger.error(f'Bad Okta response: {errorSummary}')
    else:
        logger.error('Bad Okta response')
    raise ServiceException('An error happened connecting with provider')


def delete_okta_idp(idp_id):
    try:
        status = requests.delete(
            DELETE_IDP_ENDPOINT.format(idp_id=idp_id), headers=OKTA_HEADERS
        )
        return status
    except requests.RequestException as e:
        logger.error(e.response)
        raise ServiceException('Error removing identity provider')


def delete_idp(idp_id):
    try:
        idp = IdentityProvider.objects.get(idp_id=idp_id)
        if idp.rule_id:
            delete_okta_routing_rule(idp.rule_id)
        delete_okta_idp(idp.idp_id)
        Flag.objects.update_or_create(
            name=sso_feature_flag,
            organization=idp.organization,
            defaults={'is_enabled': False},
        )
        idp.delete()
    except Exception as e:
        logger.error(f'Error when deleting idp and routing rules: {e}')
        raise e

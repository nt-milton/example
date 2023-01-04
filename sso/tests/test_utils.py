from unittest.mock import patch

import pytest
from httmock import response

from laika.utils.exceptions import ServiceException
from sso.constants import DONE_ENABLED
from sso.models import IdentityProvider, IdentityProviderDomain
from sso.utils import (
    delete_idp,
    delete_okta_idp,
    delete_okta_routing_rule,
    replace_laika_urls,
    upload_okta_idp_certificate,
    valid_okta_response,
)

valid_mocked_response = {
    'id': '1234',
    'name': 'SAML Integration',
    'status': 'ACTIVE',
    'protocol': {
        'credentials': {
            'trust': {
                'audience': 'https://laika.okta.com/testingidp/1',
                'issuer': 'https://test1.com',
            }
        },
        'endpoints': {'sso': {'url': 'https://test2.com'}},
    },
    '_links': {'acs': {'href': 'https://laika.okta.com/testingidp/2'}},
}

invalid_mocked_response = {
    'protocol': {
        'test': {
            'trust': {
                'audience': 'https://test3.com',
                'issuer': 'https://laika.okta.com/testingidp/3',
            }
        }
    }
}


def test_replace_laika_urls():
    updated_response = replace_laika_urls(valid_mocked_response)
    assert (
        updated_response['protocol']['credentials']['trust']['audience']
        == 'https://auth.heylaika.com/testingidp/1'
    )
    assert (
        updated_response['_links']['acs']['href']
        == 'https://auth.heylaika.com/testingidp/2'
    )


def test_valid_okta_response():
    assert valid_okta_response(valid_mocked_response)
    assert not valid_okta_response(invalid_mocked_response)


MOCKED_KEY_ID = '1234'
MOCKED_CERTIFICATE = '5678'
MOCKED_ERROR_CODE = 'E0090'
MOCKED_ERROR_SUMMARY = 'Error=Fail'
MOCKED_OKTA_IDP_ID = '9012'
MOCKED_OKTA_RULE_ID = 'rule1234'

okta_certificate_content = {'kid': MOCKED_KEY_ID}
okta_certificate_content_error = {
    'errorCode': MOCKED_ERROR_CODE,
    'errorSummary': MOCKED_ERROR_SUMMARY,
}
headers = {'Content-Type': 'application/json'}
okta_idp_content = {'idpId': MOCKED_OKTA_IDP_ID}


@patch('requests.post', return_value=response(200, okta_certificate_content, headers))
def test_upload_okta_idp_certificate(request_post):
    certificate = MOCKED_CERTIFICATE
    kid = upload_okta_idp_certificate(certificate)
    request_post.assert_called_once()
    assert kid == MOCKED_KEY_ID


@patch(
    'requests.post', return_value=response(200, okta_certificate_content_error, headers)
)
def test_upload_okta_idp_certificate_with_okta_error(request_post):
    certificate = MOCKED_CERTIFICATE
    with pytest.raises(ServiceException) as exc_info:
        upload_okta_idp_certificate(certificate)
    request_post.assert_called_once()
    assert exc_info.type is ServiceException
    assert exc_info.value.args[0] == 'Please provide a valid certificate'


@patch('requests.delete', return_value=response(200, okta_idp_content, headers))
def test_delete_okta_idp(request_delete):
    delete_okta_idp(MOCKED_OKTA_IDP_ID)
    request_delete.assert_called_once()


@patch('requests.delete', return_value=response(200, okta_idp_content, headers))
def test_delete_okta_routing_rule(request_delete):
    delete_okta_routing_rule(MOCKED_OKTA_RULE_ID)
    request_delete.assert_called_once()


@pytest.mark.functional(permissions=['sso.add_identityprovider'])
@patch('sso.utils.delete_okta_idp')
@patch('sso.utils.delete_okta_routing_rule')
def test_delete_idp(delete_okta_idp, delete_okta_routing_rule, graphql_organization):
    MOCKED_IDP_ID = '1234'
    MOCKED_IDP_NAME = 'Mocked Okta'
    MOCKED_RULE_ID = '987654'
    MOCKED_IDP_DOMAIN_1 = 'mock.com'
    MOCKED_IDP_DOMAIN_2 = 'mock2.com'

    idp = IdentityProvider.objects.create(
        idp_id=MOCKED_IDP_ID,
        name=MOCKED_IDP_NAME,
        organization=graphql_organization,
        rule_id=MOCKED_RULE_ID,
        state=DONE_ENABLED,
    )
    idp_insert_id = idp.id
    IdentityProviderDomain.objects.create(idp_id=idp.id, domain=MOCKED_IDP_DOMAIN_1)
    IdentityProviderDomain.objects.create(idp_id=idp.id, domain=MOCKED_IDP_DOMAIN_2)

    delete_idp(idp.idp_id)

    idp_exists = IdentityProvider.objects.filter(id=idp_insert_id)
    idp_domains_exists = IdentityProviderDomain.objects.filter(idp_id=idp_insert_id)

    delete_okta_idp.assert_called_once()
    delete_okta_routing_rule.assert_called_once()

    assert not idp_exists
    assert not idp_domains_exists


@pytest.mark.functional(permissions=['sso.add_identityprovider'])
@patch('sso.utils.delete_okta_idp')
@patch('sso.utils.delete_okta_routing_rule')
def test_delete_idp_not_exist(
    delete_okta_idp, delete_okta_routing_rule, graphql_organization
):
    MOCKED_IDP_ID = '9101'
    with pytest.raises(Exception) as exc_info:
        delete_idp(MOCKED_IDP_ID)
        assert exc_info.type is ServiceException

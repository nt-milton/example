from unittest.mock import patch

import pytest

from sso.models import IdentityProvider, IdentityProviderDomain
from sso.tests.queries import GET_IDP, GET_IDP_DOMAINS, GET_ORGANIZATION_IDP

FIRST_DOMAIN = 'alpha.com'
SECOND_DOMAIN = 'beta.com'


@pytest.mark.functional(permissions=['sso.view_identityprovider'])
@patch(
    'sso.schema.get_okta_idp',
    return_value={
        'id': '1234',
        'name': 'SAML Integration',
        'status': 'ACTIVE',
        'protocol': {
            'credentials': {
                'trust': {
                    'audience': 'https://test1.com',
                    'issuer': 'https://test2.com',
                }
            },
            'endpoints': {'sso': {'url': 'https://test3.com'}},
        },
        '_links': {'acs': {'href': 'https://test4.com'}},
    },
)
def test_get_idp(get_okta_idp_mock, graphql_client, graphql_organization):
    idp = IdentityProvider.objects.create(
        idp_id='1234', organization=graphql_organization
    )
    response = graphql_client.execute(GET_IDP, variables={'idpId': '1234'})
    get_okta_idp_mock.assert_called_once()
    assert response['data']['getIdp']['idpId'] == idp.idp_id


@pytest.mark.functional(permissions=['sso.view_identityprovider'])
def test_get_idp_domains(graphql_client, graphql_organization):
    new_idp_id = '4567'
    idp = IdentityProvider.objects.create(
        idp_id=new_idp_id, organization=graphql_organization
    )
    IdentityProviderDomain.objects.create(domain=FIRST_DOMAIN, idp=idp)
    IdentityProviderDomain.objects.create(domain=SECOND_DOMAIN, idp=idp)
    response = graphql_client.execute(GET_IDP_DOMAINS, variables={'idpId': new_idp_id})
    assert len(response['data']['getIdpDomains']['domains']) == 2
    domains = response['data']['getIdpDomains']['domains']
    assert type(domains.index(FIRST_DOMAIN)) == int
    assert type(domains.index(SECOND_DOMAIN)) == int


@pytest.mark.functional(permissions=['sso.view_identityprovider'])
def test_get_organization_idp(graphql_client, graphql_organization):
    new_idp_id = '8910'
    provider = ('Google',)
    name = 'Test idp'
    IdentityProvider.objects.create(
        idp_id=new_idp_id,
        organization=graphql_organization,
        provider=provider,
        name=name,
    )
    response = graphql_client.execute(GET_ORGANIZATION_IDP)
    assert response['data']['getOrganizationIdentityProvider']['idpId'] == new_idp_id
    assert response['data']['getOrganizationIdentityProvider']['name'] == name

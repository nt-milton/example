from unittest.mock import patch

import pytest

from feature.constants import sso_feature_flag
from sso.constants import DONE_DISABLED, DONE_ENABLED, PENDING_IDP_DATA
from sso.models import IdentityProvider, IdentityProviderDomain
from sso.tests.mutations import (
    CREATE_IDP,
    DELETE_IDP,
    DISABLE_IDP,
    ENABLE_IDP,
    SET_IDP_DOMAINS,
    UPDATE_IDP,
)

FIRST_DOMAIN = 'alpha.com'
SECOND_DOMAIN = 'beta.com'


@pytest.mark.functional(permissions=['sso.add_identityprovider'])
@patch(
    'sso.mutations.create_okta_idp',
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
@patch('sso.mutations.setup_okta_mappings.delay')
def test_create_idp(create_okta_idp_mock, setup_okta_mappings, graphql_client):
    idp_id = '1234'
    response = graphql_client.execute(CREATE_IDP, variables={'provider': 'Azure AD'})
    create_okta_idp_mock.assert_called_once()
    idp = IdentityProvider.objects.filter(idp_id=idp_id).first()
    assert idp.idp_id == idp_id
    assert idp.name == (response['data']['createIdentityProvider']['data']['name'])
    assert 'Azure AD' == idp.provider
    assert '1234' == (response['data']['createIdentityProvider']['data']['idpId'])
    setup_okta_mappings.assert_called_once()


@pytest.mark.functional(permissions=['sso.add_identityprovider'])
@patch(
    'sso.mutations.get_okta_idp',
    return_value={
        'id': '1234',
        'name': 'SAML Integration',
        'status': 'ACTIVE',
        'protocol': {
            'credentials': {
                'trust': {
                    'audience': 'https://test1.com',
                    'issuer': 'https://test2.com',
                    'kid': '123456',
                }
            },
            'endpoints': {'sso': {'url': 'https://test3.com'}},
        },
        '_links': {'acs': {'href': 'https://test4.com'}},
    },
)
@patch(
    'sso.mutations.update_okta_idp',
    return_value={
        'id': '1234',
        'name': 'SAML Integration',
        'status': 'ACTIVE',
        'protocol': {
            'credentials': {
                'trust': {
                    'audience': 'https://test1.com',
                    'issuer': 'https://test2.com',
                    'kid': '123456',
                }
            },
            'endpoints': {'sso': {'url': 'https://test3.com'}},
        },
        '_links': {'acs': {'href': 'https://test4.com'}},
    },
)
@patch('sso.mutations.get_okta_idp_certificate', return_value='7891011')
@patch('sso.mutations.upload_okta_idp_certificate', return_value='123')
def test_update_idp(
    get_okta_idp,
    update_okta_idp_mock,
    get_okta_idp_certificate,
    upload_okta_idp_certificate,
    graphql_client,
    graphql_organization,
):
    IdentityProvider.objects.create(
        idp_id='1234', organization=graphql_organization, name='IDP1'
    )
    response = graphql_client.execute(
        UPDATE_IDP, variables={'idpId': '1234', 'name': 'IDP2', 'certificate': '123456'}
    )
    get_okta_idp.assert_called_once()
    update_okta_idp_mock.assert_called_once()
    get_okta_idp_certificate.assert_called_once()
    upload_okta_idp_certificate.assert_called_once()
    updated_idp = IdentityProvider.objects.filter(idp_id='1234').first()
    assert updated_idp.name == 'IDP2'
    assert response['data']['updateIdentityProviderById']['data']['status'] == 'Success'


@pytest.mark.functional(permissions=['sso.add_identityprovider'])
@patch('sso.mutations.update_okta_rule', return_value='9999')
def test_set_idp_domains(update_okta_rule, graphql_client, graphql_organization):
    new_idp_id = '8910'
    IdentityProvider.objects.create(
        idp_id=new_idp_id, organization=graphql_organization, state=DONE_ENABLED
    )
    graphql_client.execute(
        SET_IDP_DOMAINS,
        variables={'idpId': new_idp_id, 'domains': [FIRST_DOMAIN, SECOND_DOMAIN]},
    )
    idp_domains = IdentityProviderDomain.objects.filter(idp__idp_id=new_idp_id)
    update_okta_rule.assert_called_once()
    assert len(idp_domains) == 2
    assert any(d for d in idp_domains if d.domain == FIRST_DOMAIN)
    assert any(d for d in idp_domains if d.domain == SECOND_DOMAIN)
    idp = IdentityProvider.objects.get(idp_id='8910')
    assert idp.rule_id == '9999'


@pytest.mark.functional(permissions=['sso.add_identityprovider'])
@patch('sso.mutations.delete_okta_routing_rule', return_value={'status': 200})
def test_disable_idp_valid(
    delete_okta_routing_rule_mock, graphql_client, graphql_organization
):
    new_idp_id = '1234'
    provider = ('Okta',)
    name = 'Test disable idp'
    state = DONE_ENABLED
    IdentityProvider.objects.create(
        idp_id=new_idp_id,
        organization=graphql_organization,
        provider=provider,
        name=name,
        state=state,
        rule_id='4321',
    )
    graphql_client.execute(DISABLE_IDP, variables={'idpId': new_idp_id})
    idp = IdentityProvider.objects.filter(idp_id=new_idp_id).first()
    flag = graphql_organization.is_flag_active(sso_feature_flag)
    delete_okta_routing_rule_mock.assert_called_once()
    assert idp.state == DONE_DISABLED
    assert not flag


@pytest.mark.functional(permissions=['sso.add_identityprovider'])
@patch('sso.mutations.delete_okta_routing_rule', return_value={'status': 200})
def test_disable_idp_invalid(
    delete_okta_routing_rule_mock, graphql_client, graphql_organization
):
    new_idp_id = '12345'
    provider = ('Okta',)
    name = 'Test disable idp'
    state = PENDING_IDP_DATA
    IdentityProvider.objects.create(
        idp_id=new_idp_id,
        organization=graphql_organization,
        provider=provider,
        name=name,
        state=state,
    )
    graphql_client.execute(DISABLE_IDP, variables={'idpId': new_idp_id})
    idp = IdentityProvider.objects.filter(idp_id=new_idp_id).first()
    assert not delete_okta_routing_rule_mock.called
    assert idp.state == PENDING_IDP_DATA


@pytest.mark.functional(permissions=['sso.add_identityprovider'])
@patch('sso.mutations.create_okta_routing_rule', return_value={'id': '8888'})
def test_enable_idp_valid(
    create_okta_routing_rule_mock, graphql_client, graphql_organization
):
    new_idp_id = '123456'
    provider = ('Okta',)
    name = 'Test enable idp'
    state = DONE_DISABLED
    IdentityProvider.objects.create(
        idp_id=new_idp_id,
        organization=graphql_organization,
        provider=provider,
        name=name,
        state=state,
    )
    graphql_client.execute(ENABLE_IDP, variables={'idpId': new_idp_id})
    idp = IdentityProvider.objects.filter(idp_id=new_idp_id).first()
    flag = graphql_organization.is_flag_active(sso_feature_flag)
    create_okta_routing_rule_mock.assert_called_once()
    assert idp.state == DONE_ENABLED
    assert flag


@pytest.mark.functional(permissions=['sso.add_identityprovider'])
@patch('sso.mutations.create_okta_routing_rule', return_value={'id': '8888'})
def test_enable_idp_invalid(
    create_okta_routing_rule_mock, graphql_client, graphql_organization
):
    new_idp_id = '4321'
    provider = ('Okta',)
    name = 'Test enable idp'
    state = PENDING_IDP_DATA
    IdentityProvider.objects.create(
        idp_id=new_idp_id,
        organization=graphql_organization,
        provider=provider,
        name=name,
        state=state,
    )
    graphql_client.execute(ENABLE_IDP, variables={'idpId': new_idp_id})
    idp = IdentityProvider.objects.filter(idp_id=new_idp_id).first()
    assert not create_okta_routing_rule_mock.called
    assert idp.state == PENDING_IDP_DATA


@pytest.mark.functional(permissions=['sso.delete_identityprovider'])
@patch('sso.mutations.delete_idp')
def test_delete_idp(delete_idp, graphql_client):
    IDP_ID = '123456'
    graphql_client.execute(DELETE_IDP, variables={'idpId': IDP_ID})

    delete_idp.assert_called_once()

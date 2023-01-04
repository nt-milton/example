import logging

import graphene
import requests

import sso.errors as errors
from laika.decorators import laika_service
from sso.models import IdentityProvider, IdentityProviderDomain
from sso.mutations import (
    CreateIdentityProvider,
    DeleteIdentityProvider,
    DisableIdentityProvider,
    EnableIdentityProvider,
    SetIdentityProviderDomains,
    UpdateIdentityProviderById,
)
from sso.types import (
    IdentityProviderClientFields,
    IdentityProviderDomainResponseType,
    IdentityProviderLaikaFields,
    IdentityProviderResponseType,
    OrganizationIdentityProviderType,
)
from sso.utils import get_okta_idp

logger = logging.getLogger('sso')


class Query(object):
    get_idp = graphene.Field(
        IdentityProviderResponseType, idp_id=graphene.String(required=True)
    )

    get_idp_domains = graphene.Field(
        IdentityProviderDomainResponseType, idp_id=graphene.String(required=True)
    )

    get_organization_identity_provider = graphene.Field(
        OrganizationIdentityProviderType
    )

    @laika_service(
        permission='sso.view_identityprovider',
        exception_msg='Failed to get identity provider. Please try again',
    )
    def resolve_get_idp(self, info, **kwargs):
        idp_id = kwargs.get('idp_id', None)
        idp = IdentityProvider.objects.filter(idp_id=idp_id).first()
        if not idp:
            return IdentityProviderResponseType(error=errors.INVALID_IDP, idp_id=None)
        try:
            response = get_okta_idp(idp.idp_id)
            if 'errorCode' not in response:
                return IdentityProviderResponseType(
                    idp_id=response['id'],
                    name=idp.name,
                    status=response['status'],
                    client_fields=IdentityProviderClientFields(
                        issuer_uri=response['protocol']['credentials']['trust'][
                            'issuer'
                        ],
                        sso_url=response['protocol']['endpoints']['sso']['url'],
                    ),
                    laika_fields=IdentityProviderLaikaFields(
                        assertion_consumer_service_url=response['_links']['acs'][
                            'href'
                        ],
                        audience_uri=response['protocol']['credentials']['trust'][
                            'audience'
                        ],
                    ),
                    state=idp.state,
                )
            else:
                return IdentityProviderResponseType(idp_id=idp.idp_id)
        except requests.RequestException:
            return IdentityProviderResponseType(error=errors.GET_IDP_ERROR, idp_id=None)

    @laika_service(
        permission='sso.view_identityprovider',
        exception_msg='Failed to get identity provider. Please try again',
    )
    def resolve_get_idp_domains(self, info, **kwargs):
        idp_id = kwargs.get('idp_id')
        full_domains = IdentityProviderDomain.objects.filter(idp__idp_id=idp_id)
        domains = []
        for domain in full_domains:
            domains.append(domain.domain)
        return IdentityProviderDomainResponseType(domains=domains, error=None)

    @laika_service(
        permission='sso.view_identityprovider',
        exception_msg='Failed to get identity provider. Please try again',
    )
    def resolve_get_organization_identity_provider(self, info, **kwargs):
        try:
            organization = info.context.user.organization
            idp = IdentityProvider.objects.filter(
                organization__id=organization.id
            ).first()
            if idp:
                return OrganizationIdentityProviderType(
                    idp_id=idp.idp_id,
                    provider=idp.provider,
                    name=idp.name,
                    state=idp.state,
                )
            return None
        except Exception as e:
            logger.info('Organization has no SAML configuration', e.message)
            return None


class Mutation(graphene.ObjectType):
    create_identity_provider = CreateIdentityProvider.Field()
    update_identity_provider_by_id = UpdateIdentityProviderById.Field()
    set_identity_provider_domains = SetIdentityProviderDomains.Field()
    disable_identity_provider = DisableIdentityProvider.Field()
    enable_identity_provider = EnableIdentityProvider.Field()
    delete_identity_provider = DeleteIdentityProvider.Field()

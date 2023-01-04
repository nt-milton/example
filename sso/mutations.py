import logging

import graphene
import requests

import sso.errors as errors
from laika.decorators import laika_service
from laika.utils.exceptions import ServiceException
from sso.constants import DONE_DISABLED, DONE_ENABLED
from sso.models import IdentityProvider, IdentityProviderDomain
from sso.tasks import delete_inactive_okta_users_task, setup_okta_mappings
from sso.types import (
    IdentityProviderClientFields,
    IdentityProviderDomainResponseType,
    IdentityProviderLaikaFields,
    IdentityProviderResponseType,
    UpdateIdentityProviderResponseType,
)
from sso.utils import (
    activate_feature_flags_on_idp_activate,
    create_okta_idp,
    create_okta_routing_rule,
    delete_idp,
    delete_okta_routing_rule,
    disable_feature_flags_on_idp_disable,
    get_okta_idp,
    get_okta_idp_certificate,
    remove_header_from_certificate,
    update_okta_idp,
    update_okta_rule,
    upload_okta_idp_certificate,
    valid_domain,
)

logger = logging.getLogger('sso')


def generate_identity_provider_response(okta_idp):
    return IdentityProviderResponseType(
        idp_id=okta_idp['id'],
        name=okta_idp['name'],
        status=okta_idp['status'],
        client_fields=IdentityProviderClientFields(
            issuer_uri=okta_idp['protocol']['credentials']['trust']['issuer'],
            sso_url=okta_idp['protocol']['endpoints']['sso']['url'],
        ),
        laika_fields=IdentityProviderLaikaFields(
            assertion_consumer_service_url=okta_idp['_links']['acs']['href'],
            audience_uri=okta_idp['protocol']['credentials']['trust']['audience'],
        ),
    )


def get_updated_okta_idp(okta_idp, client_fields):
    updated_okta_idp = okta_idp
    idp_id = okta_idp['id']
    issuer_uri = client_fields['issuer_uri']
    sso_url = client_fields['sso_url']
    if client_fields['certificate']:
        key_id = okta_idp['protocol']['credentials']['trust']['kid']
        try:
            okta_certificate = get_okta_idp_certificate(key_id)
            stripped_cert = remove_header_from_certificate(client_fields['certificate'])
            if okta_certificate != stripped_cert:
                new_key_id = upload_okta_idp_certificate(stripped_cert)
                updated_okta_idp['protocol']['credentials']['trust']['kid'] = new_key_id
        except requests.RequestException:
            logger.warning(f'Failed to update key for idp {idp_id} from Okta')
            raise ServiceException(errors.GET_IDP_KEY_ERROR)
    if client_fields['issuer_uri']:
        okta_idp['protocol']['credentials']['trust']['issuer'] = issuer_uri
    if sso_url:
        okta_idp['protocol']['endpoints']['sso']['url'] = sso_url
        okta_idp['protocol']['endpoints']['sso']['destination'] = sso_url
    return updated_okta_idp


def get_okta_idp_from_api(idp_id):
    try:
        return get_okta_idp(idp_id)
    except requests.RequestException:
        logger.warning(f'Failed to get idp {idp_id} from Okta')
        raise ServiceException(errors.GET_IDP_KEY_ERROR)


def update_okta_idp_with_api(okta_idp):
    idp_id = okta_idp['id']
    try:
        update_okta_idp(okta_idp['id'], okta_idp)
    except requests.RequestException:
        logger.warning(f'Failed to update idp {idp_id} from Okta')
        raise ServiceException(errors.UPDATE_IDP_ERROR)


def update_idp_entity(idp_id, name, state):
    if name:
        idp = IdentityProvider.objects.get(idp_id=idp_id)
        idp.name = name
        if state:
            idp.state = state
        idp.save()


class ToggleIdentityProviderType(graphene.ObjectType):
    idp_id = graphene.String()
    error = graphene.String()


class DeleteIdentityProviderType(graphene.ObjectType):
    idp_id = graphene.String()


class CreateIdentityProvider(graphene.Mutation):
    data = graphene.Field(IdentityProviderResponseType)

    class Arguments:
        provider = graphene.String(required=True)

    @laika_service(
        permission='sso.add_identityprovider',
        exception_msg='You don\'t have permission to create idp',
    )
    def mutate(self, info, **kwargs):
        organization = info.context.user.organization
        provider = kwargs.get('provider')
        try:
            okta_idp = create_okta_idp(organization, provider)
            idp = IdentityProvider(
                idp_id=okta_idp['id'],
                name=okta_idp['name'],
                organization=organization,
                provider=provider,
            )
            idp.save()
            setup_okta_mappings.delay(
                okta_idp['id'], organization.id, organization.name, idp.provider
            )
            return CreateIdentityProvider(
                data=generate_identity_provider_response(okta_idp)
            )
        except requests.RequestException:
            return IdentityProviderResponseType(
                error=errors.CREATE_IDP_ERROR, idp_id=None
            )


class UpdateIdentityProviderById(graphene.Mutation):
    data = graphene.Field(UpdateIdentityProviderResponseType)

    class Arguments:
        idp_id = graphene.String(required=True)
        name = graphene.String()
        issuer_uri = graphene.String()
        sso_url = graphene.String()
        certificate = graphene.String()
        state = graphene.String()

    @laika_service(
        permission='sso.add_identityprovider',
        exception_msg='You don\'t have permission to create idp',
    )
    def mutate(self, info, **kwargs):
        idp_id = kwargs.get('idp_id')
        name = kwargs.get('name')
        client_fields = {
            'issuer_uri': kwargs.get('issuer_uri'),
            'sso_url': kwargs.get('sso_url'),
            'certificate': kwargs.get('certificate'),
        }
        state = kwargs.get('state')
        okta_idp = get_okta_idp_from_api(idp_id)
        updated_okta_idp = get_updated_okta_idp(okta_idp, client_fields)
        update_okta_idp_with_api(updated_okta_idp)
        update_idp_entity(idp_id, name, state)
        data = UpdateIdentityProviderResponseType(status='Success')
        return UpdateIdentityProviderById(data=data)


class SetIdentityProviderDomains(graphene.Mutation):
    data = graphene.Field(IdentityProviderDomainResponseType)

    class Arguments:
        idp_id = graphene.String(required=True)
        domains = graphene.List(graphene.String)
        state = graphene.String()

    @laika_service(
        permission='sso.add_identityprovider',
        exception_msg='You don\'t have permission to add idp domains',
    )
    def mutate(self, info, **kwargs):
        idp_id = kwargs.get('idp_id')
        domains = kwargs.get('domains')
        state = kwargs.get('state')
        added_domains = []
        idp = IdentityProvider.objects.filter(idp_id=idp_id).first()
        IdentityProviderDomain.objects.filter(idp__idp_id=idp_id).delete()
        for domain in domains:
            if valid_domain(domain):
                IdentityProviderDomain.objects.create(domain=domain, idp=idp)
                added_domains.append(domain)
            else:
                data = IdentityProviderDomainResponseType(error='Domains are invalid')
                return SetIdentityProviderDomains(data=data)
        idp.rule_id = update_okta_rule(idp, added_domains, state)
        if state:
            idp.state = state
        idp.save(update_fields=['rule_id', 'state'])
        response = IdentityProviderDomainResponseType(domains=added_domains, error=None)
        return SetIdentityProviderDomains(data=response)


class DisableIdentityProvider(graphene.Mutation):
    data = graphene.Field(ToggleIdentityProviderType)

    class Arguments:
        idp_id = graphene.String(required=True)

    @laika_service(
        permission='sso.add_identityprovider',
        exception_msg='You don\'t have permission to disable Identity Provider',
    )
    def mutate(self, info, **kwargs):
        idp_id = kwargs.get('idp_id')
        try:
            idp = IdentityProvider.objects.get(idp_id=idp_id)
            if idp.state != DONE_ENABLED:
                raise ServiceException('Only enabled configurations can be disabled')
            if idp.rule_id:
                try:
                    delete_okta_routing_rule(idp.rule_id)
                except requests.RequestException as e:
                    logger.warning(
                        f'Error happened when deleting okta routing rule: {e}'
                    )
                    raise ServiceException(
                        'An error  happened connecting with provider'
                    )
            idp.state = DONE_DISABLED
            idp.rule_id = None
            idp.save(update_fields=['state', 'rule_id'])
            disable_feature_flags_on_idp_disable(info.context.user.organization)
            response = ToggleIdentityProviderType(idp_id=idp_id)
            return DisableIdentityProvider(data=response)
        except IdentityProvider.DoesNotExist:
            raise ServiceException('Identity Provider not found')


class EnableIdentityProvider(graphene.Mutation):
    data = graphene.Field(ToggleIdentityProviderType)

    class Arguments:
        idp_id = graphene.String(required=True)

    @laika_service(
        permission='sso.add_identityprovider',
        exception_msg='You do not have permission to enable Identity Provider',
    )
    def mutate(self, info, **kwargs):
        idp_id = kwargs.get('idp_id')
        organization_name = info.context.user.organization.name
        idp = IdentityProvider.objects.get(idp_id=idp_id)
        if idp.state != DONE_DISABLED:
            raise ServiceException('Only disabled configurations can be enabled')
        domains = list(
            IdentityProviderDomain.objects.filter(idp__idp_id=idp_id).values_list(
                'domain', flat=True
            )
        )
        try:
            rule_response = create_okta_routing_rule(
                organization_name, idp_id, domains=domains
            )
        except requests.RequestException:
            raise ServiceException('Error connection with provider')
        idp.rule_id = rule_response['id']
        idp.state = DONE_ENABLED
        idp.save(update_fields=['rule_id', 'state'])
        activate_feature_flags_on_idp_activate(info.context.user.organization)
        delete_inactive_okta_users_task.delay(idp.organization.id)
        response = ToggleIdentityProviderType(idp_id=idp_id, error=None)
        return EnableIdentityProvider(data=response)


class DeleteIdentityProvider(graphene.Mutation):
    data = graphene.Field(DeleteIdentityProviderType)

    class Arguments:
        idp_id = graphene.String(required=True)

    @laika_service(
        permission='sso.delete_identityprovider',
        exception_msg='''
            You do not have permission to delete this Identity Provider
        ''',
    )
    def mutate(self, info, **kwargs):
        try:
            idp_id = kwargs.get('idp_id')
            delete_idp(idp_id)
            return DeleteIdentityProvider(
                data=DeleteIdentityProviderType(idp_id=idp_id)
            )
        except Exception as e:
            logger.error(f'Error deleting IDP: {e}')
            raise ServiceException('An error happened, please contact an administrator')

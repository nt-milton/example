import graphene


class IdentityProviderClientFields(graphene.ObjectType):
    issuer_uri = graphene.String()
    sso_url = graphene.String()


class IdentityProviderLaikaFields(graphene.ObjectType):
    assertion_consumer_service_url = graphene.String()
    audience_uri = graphene.String()


class IdentityProviderResponseType(graphene.ObjectType):
    idp_id = graphene.String()
    name = graphene.String()
    status = graphene.String()
    client_fields = graphene.Field(IdentityProviderClientFields)
    laika_fields = graphene.Field(IdentityProviderLaikaFields)
    error = graphene.String()
    state = graphene.String()


class UpdateIdentityProviderResponseType(graphene.ObjectType):
    status = graphene.String()
    error = graphene.String()


class IdentityProviderDomainResponseType(graphene.ObjectType):
    domains = graphene.List(graphene.String)
    error = graphene.String()


class OrganizationIdentityProviderType(graphene.ObjectType):
    idp_id = graphene.String()
    provider = graphene.String()
    name = graphene.String()
    error = graphene.String()
    state = graphene.String()


class ToggleIdentityProviderType(graphene.ObjectType):
    idp_id = graphene.String()
    error = graphene.String()


class DeleteIdentityProviderType(graphene.ObjectType):
    idp_id = graphene.String()

import graphene


class SeedOrganizationInput(graphene.InputObjectType):
    organization_id = graphene.UUID(required=True)
    profile_id = graphene.UUID(required=True)

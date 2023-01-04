import graphene


class FeatureFlagInput(graphene.InputObjectType):
    id = graphene.String(required=True)
    name = graphene.String(required=True)
    display_name = graphene.String(required=True)
    is_enabled = graphene.Boolean(required=True)


class UpdateFeatureInput(graphene.InputObjectType):
    organization_id = graphene.String(required=True)
    flags = graphene.List(FeatureFlagInput, request=True)

import graphene


class AddManualTagInput(graphene.InputObjectType):
    name = graphene.String()
    is_manual = graphene.Boolean(default_value=False)
    organization_id = graphene.String()


class InputTagType(graphene.InputObjectType):
    id = graphene.String()
    name = graphene.String()

import graphene


class TagType(graphene.ObjectType):
    id = graphene.String(required=True)
    name = graphene.String(required=True)
    organization_name = graphene.String(required=True)
    is_manual = graphene.Boolean(required=True)


class TagsResponseType(graphene.ObjectType):
    data = graphene.List(TagType)

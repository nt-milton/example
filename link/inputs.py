import graphene

from laika import types


class UpdateLinkInput(types.DjangoInputObjectBaseType):
    link_id = graphene.String(required=True)
    is_enabled = graphene.Boolean()
    expiration_date = graphene.Date()
    time_zone = graphene.String()

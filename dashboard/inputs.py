import graphene

from laika import types


class UpdateDashboardItemInput(types.DjangoInputObjectBaseType):
    unique_action_item_id = graphene.String(required=True)
    seen = graphene.Boolean()

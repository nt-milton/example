import graphene


class UpdateControlGroupInput(graphene.InputObjectType):
    id = graphene.ID(required=True)
    name = graphene.String()
    start_date = graphene.DateTime()
    due_date = graphene.DateTime()
    sort_order = graphene.Int()


class CreateControlGroupInput(graphene.InputObjectType):
    organization_id = graphene.UUID(required=True)


class DeleteGroupInput(graphene.InputObjectType):
    id = graphene.ID(required=True)
    organization_id = graphene.String()


class ControlGroupSortOrder(graphene.InputObjectType):
    id = graphene.Int(required=True)
    sort_order = graphene.String(required=True)


class UpdateControlGroupSortOrderInput(graphene.InputObjectType):
    organization_id = graphene.UUID(required=True)
    control_groups = graphene.List(ControlGroupSortOrder)


class UpdateControlSortOrderInput(graphene.InputObjectType):
    controls = graphene.List(graphene.UUID)


class MoveControlsToControlGroupInput(graphene.InputObjectType):
    organization_id = graphene.UUID()
    group_id = graphene.Int(required=True)
    control_ids = graphene.List(graphene.UUID, required=True)

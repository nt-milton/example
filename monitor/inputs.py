import graphene


class MonitorExclusionInputType(graphene.InputObjectType):
    data_indexes = graphene.List(graphene.Int)
    justification = graphene.String(required=True)


class BulkWatchInput(graphene.InputObjectType):
    event_type = graphene.String()
    ids = graphene.List(graphene.ID)

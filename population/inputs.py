import graphene


class PopulationInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    population_id = graphene.String(required=True)


class LaikaSourcePopulationInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    population_id = graphene.String(required=True)
    source = graphene.String(required=True)

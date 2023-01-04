import graphene


class ActionItemEvidenceType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    description = graphene.String()
    link = graphene.String()
    evidence_type = graphene.String()
    date = graphene.DateTime()
    linkable = graphene.Boolean()
    content_id = graphene.String()

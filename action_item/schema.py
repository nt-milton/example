import graphene

from action_item.mutations import AddActionItemEvidence, DeleteActionItemEvidence
from control.types import EvidenceType
from evidence.models import Evidence


class Mutation(graphene.ObjectType):
    add_action_item_evidence = AddActionItemEvidence.Field()
    delete_action_item_evidence = DeleteActionItemEvidence.Field()


class Query(object):
    action_item_evidences = graphene.List(EvidenceType, id=graphene.Int(required=True))

    def resolve_action_item_evidences(self, info, **kwargs):
        id = kwargs.get('id')

        return Evidence.objects.filter(action_items__id=id)

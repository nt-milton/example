import graphene

from evidence.mutations import (
    AsyncExport,
    LinkTagsToEvidence,
    RenameEvidence,
    UnlinkTagsToEvidence,
    UpdateEvidence,
)


class Mutation(graphene.ObjectType):
    rename_evidence = RenameEvidence.Field()
    async_export = AsyncExport.Field()
    link_tags = LinkTagsToEvidence.Field()
    unlink_tags = UnlinkTagsToEvidence.Field()
    update_evidence = UpdateEvidence.Field()

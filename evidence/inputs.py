import graphene


class EvidenceInput(graphene.InputObjectType):
    evidence_id = graphene.Int(required=True)
    new_name = graphene.String()
    description = graphene.String(default_value='')


class RenameEvidenceInput(graphene.InputObjectType):
    evidence_id = graphene.Int(required=True)
    new_name = graphene.String(required=True)
    # Where is coming from, OrganizationVendor, Dataroom
    sender = graphene.String()
    # Id of the OrganizationVendor, Dataroom
    reference_id = graphene.String()
    organization_id = graphene.String()


class ExportRequestInput(graphene.InputObjectType):
    dataroom_id = graphene.String()
    evidence_id = graphene.List(graphene.Int)
    export_type = graphene.String(required=True)
    time_zone = graphene.String()
    organization_id = graphene.String()


class LinkTagsToEvidenceInput(graphene.InputObjectType):
    tag_ids = graphene.List(graphene.Int, required=True)
    new_manual_tags = graphene.List(graphene.String)
    evidence_id = graphene.Int(required=True)
    organization_id = graphene.String()

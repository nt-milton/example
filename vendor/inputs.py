import graphene

from laika import types


class AddOrganizationVendorDocumentsInput(graphene.InputObjectType):
    id = graphene.Int(required=True)
    uploaded_files = graphene.List(types.InputFileType)
    policies = graphene.List(graphene.String)
    other_evidence = graphene.List(graphene.String)
    teams = graphene.List(graphene.String)
    officers = graphene.List(graphene.String)
    time_zone = graphene.String(required=True)


class DeleteOrganizationVendorDocumentsInput(graphene.InputObjectType):
    id = graphene.Int(required=True)
    documents = graphene.List(graphene.String)

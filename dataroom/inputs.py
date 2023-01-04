import graphene

from dataroom.models import Dataroom
from laika import types


class DataroomInput(object):
    name = graphene.String()


class CreateDataroomInput(DataroomInput, types.DjangoInputObjectBaseType):
    name = graphene.String(required=True)

    class InputMeta:
        model = Dataroom


class ToggleDataroomInput(graphene.InputObjectType):
    id = graphene.Int(required=True)
    is_soft_deleted = graphene.Boolean(required=True)


class AddDataroomDocumentsInput(graphene.InputObjectType):
    id = graphene.Int(required=True)
    uploaded_files = graphene.List(types.InputFileType)
    policies = graphene.List(graphene.String)
    documents = graphene.List(graphene.String)
    other_evidence = graphene.List(graphene.String)
    teams = graphene.List(graphene.String)
    officers = graphene.List(graphene.String)
    time_zone = graphene.String(required=True)
    organization_id = graphene.String()


class DeleteDataroomDocumentsInput(graphene.InputObjectType):
    id = graphene.Int(required=True)
    documents = graphene.List(graphene.String)

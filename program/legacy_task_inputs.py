import graphene

from laika.types import InputFileType


class TaskEvidenceInput(graphene.InputObjectType):
    id = graphene.UUID(required=True)
    teams = graphene.List(graphene.UUID)
    officers = graphene.List(graphene.UUID)
    policies = graphene.List(graphene.UUID)
    documents = graphene.List(graphene.String)
    s3_files = graphene.List(InputFileType)
    other_evidence = graphene.List(graphene.String)
    time_zone = graphene.String()


class DeleteEvidenceInput(graphene.InputObjectType):
    id = graphene.UUID(required=True)
    teams = graphene.List(graphene.String)
    officers = graphene.List(graphene.String)
    policies = graphene.List(graphene.String)
    documents = graphene.List(graphene.String)
    s3_files = graphene.List(graphene.String)
    laika_papers = graphene.List(graphene.String)


class DeleteTasksInput(graphene.InputObjectType):
    ids = graphene.List(graphene.String)

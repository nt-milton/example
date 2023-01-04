import graphene

from laika import types


class ActionItemsNoteLaikaPaperInput(graphene.InputObjectType):
    laika_paper_title = graphene.String(required=True)
    laika_paper_content = graphene.String(default_value='', required=True)


class ActionItemEvidenceInput(graphene.InputObjectType):
    id = graphene.String(required=True)
    files = graphene.List(types.InputFileType)
    policies = graphene.List(graphene.String)
    documents = graphene.List(graphene.String)
    other_evidence = graphene.List(graphene.String)
    teams = graphene.List(graphene.String)
    officers = graphene.List(graphene.String)
    time_zone = graphene.String(required=True)
    laika_paper = graphene.Field(
        lambda: ActionItemsNoteLaikaPaperInput, name="laika_paper"
    )


class DeleteActionItemEvidenceInput(graphene.InputObjectType):
    id = graphene.Int(required=True)
    evidence = graphene.List(graphene.String)

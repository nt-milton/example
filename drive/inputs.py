import graphene

from laika import types


class AddDriveEvidenceInput(graphene.InputObjectType):
    uploaded_files = graphene.List(types.InputFileType)
    time_zone = graphene.String(required=True)
    is_onboarding = graphene.Boolean()
    description = graphene.String(default_value='')
    organization_id = graphene.String()


class CreateLaikaPaperInput(graphene.InputObjectType):
    template_id = graphene.Int()
    organization_id = graphene.String()


class UpdateLaikaPaperInput(graphene.InputObjectType):
    laika_paper_id = graphene.Int()
    laika_paper_content = graphene.String(default_value='')
    organization_id = graphene.String()


class AddLaikaPaperIgnoreWordInput(graphene.InputObjectType):
    laika_paper_id = graphene.Int(required=True)
    laika_paper_language = graphene.String(required=True)
    laika_paper_ignore_word = graphene.String(required=True)


class DeleteDriveEvidenceInput(graphene.InputObjectType):
    evidence_ids = graphene.List(graphene.String)
    organization_id = graphene.String()


class UpdateDocumentOwnerInput(graphene.InputObjectType):
    evidence_id = graphene.Int(required=True)
    owner_email = graphene.String(required=True)
    organization_id = graphene.String()


class UpdateDocumentInput(graphene.InputObjectType):
    evidence_id = graphene.Int(required=True)
    description = graphene.String()

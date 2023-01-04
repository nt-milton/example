import graphene

from comment.inputs import CommentInput
from laika import types

from .models import Audit


class CreateAuditInput(types.DjangoInputObjectBaseType):
    name = graphene.String(required=True)
    audit_type = graphene.String(required=True)
    audit_configuration = graphene.JSONString(required=True)
    audit_firm_name = graphene.String(required=True)

    class InputMeta:
        model = Audit


class CheckStatusFieldInput(types.DjangoInputObjectBaseType):
    field = graphene.String(required=True)
    status_id = graphene.String(required=True)
    audit_id = graphene.String(required=True)


class UpdateAuditStageInput(types.DjangoInputObjectBaseType):
    id = graphene.String(required=True)
    enable_stage = graphene.String(required=True)


class UpdateAuditorStepInput(types.DjangoInputObjectBaseType):
    audit_id = graphene.String(required=True)
    status_id = graphene.String(required=True)
    field = graphene.String(required=True)
    value = graphene.String(required=True)
    file_name = graphene.String()


class UpdateAuditDetailsInput(types.DjangoInputObjectBaseType):
    audit_id = graphene.String(required=True)
    name = graphene.String(required=True)
    legal_name = graphene.String(required=True)
    short_name = graphene.String(required=True)
    system_name = graphene.String(required=True)
    audit_configuration = graphene.JSONString(required=True)


class AssignAuditToAuditorInput(types.DjangoInputObjectBaseType):
    audit_id = graphene.String(required=True)
    auditor_emails = graphene.List(graphene.String, required=True)
    role = graphene.String(required=True)


class UpdateAuditorRoleInAuditTeamInput(types.DjangoInputObjectBaseType):
    audit_id = graphene.String(required=True)
    auditor_email = graphene.String(required=True)
    role = graphene.String(required=True)


class RemoveAuditorFromAuditInput(types.DjangoInputObjectBaseType):
    audit_id = graphene.String(required=True)
    auditor_email = graphene.String(required=True)


class CreateAuditUserInput(types.DjangoInputObjectBaseType):
    first_name = graphene.String(required=True)
    last_name = graphene.String(required=True)
    email = graphene.String(required=True)
    permission = graphene.String(required=True)


class UpdateAuditUserInput(types.DjangoInputObjectBaseType):
    first_name = graphene.String(required=True)
    last_name = graphene.String(required=True)
    email = graphene.String(required=True)
    role = graphene.String(required=True)


class UpdateAuditorUserPreferencesInput(types.DjangoInputObjectBaseType):
    email = graphene.String(required=True)
    user_preferences = graphene.JSONString()


class CreateDraftReportReplyInput(CommentInput, graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    comment_id = graphene.String(required=True)


class UpdateDraftReportReplyInput(CommentInput, graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    comment_id = graphene.String(required=True)
    reply_id = graphene.String(required=True)


class DeleteDraftReportReplyInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    comment_id = graphene.String(required=True)
    reply_id = graphene.String(required=True)


class ApproveAuditeeDraftReportInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)

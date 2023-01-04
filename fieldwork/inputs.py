import graphene

from comment.inputs import CommentInput
from laika import types

from .models import Evidence
from .types import evidence_status_enum


class AssignEvidenceInput(graphene.InputObjectType):
    email = graphene.String(required=True)
    evidence_ids = graphene.List(graphene.String, required=True)
    audit_id = graphene.String(required=True)


class UpdateEvidenceLaikaReviewedInput(graphene.InputObjectType):
    evidence_ids = graphene.List(graphene.String, required=True)
    audit_id = graphene.String(required=True)
    review_all = graphene.Boolean()


class UpdateEvidenceStatusInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    ids = graphene.List(graphene.String, required=True)
    status = evidence_status_enum(required=True)
    transition_reasons = graphene.String()
    extra_notes = graphene.String()


class EvidenceMonitorAttachmentInput(graphene.InputObjectType):
    id = graphene.String()
    name = graphene.String()


class AddEvidenceAttachmentInput(graphene.InputObjectType):
    id = graphene.String(required=True)
    sample_id = graphene.String()
    uploaded_files = graphene.List(types.InputFileType)
    policies = graphene.List(graphene.String)
    documents = graphene.List(graphene.String)
    officers = graphene.List(graphene.String)
    teams = graphene.List(graphene.String)
    objects_ids = graphene.List(graphene.String)
    monitors = graphene.List(EvidenceMonitorAttachmentInput)
    vendors = graphene.List(graphene.String)
    trainings = graphene.List(graphene.String)
    time_zone = graphene.String(required=True)


class AddEvidenceAttachmentAuditorInput(graphene.InputObjectType):
    id = graphene.String(required=True)
    auditId = graphene.String(required=True)
    uploaded_files = graphene.List(types.InputFileType)
    policies = graphene.List(graphene.String)
    documents = graphene.List(graphene.String)


class DeleteEvidenceAttachmentInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    evidence_id = graphene.String(required=True)
    attachment_id = graphene.String(required=True)


class DeleteAuditorEvidenceAttachmentInput(graphene.InputObjectType):
    attachment_id = graphene.String(required=True)
    evidence_id = graphene.String(required=True)
    audit_id = graphene.String(required=True)


class UpdateEvidenceInput(types.DjangoInputObjectBaseType):
    audit_id = graphene.String()
    evidence_id = graphene.String()
    read = graphene.Boolean()
    description = graphene.String()
    status = evidence_status_enum()
    is_laika_reviewed = graphene.Boolean()
    assignee_email = graphene.String()
    transition_reasons = graphene.String()
    extra_notes = graphene.String()

    class InputMeta:
        model = Evidence


class RenameAttachmentInput(graphene.InputObjectType):
    evidence_id = graphene.String(required=True)
    attachment_id = graphene.String(required=True)
    new_name = graphene.String(required=True)


class EvidenceFilterInput(graphene.InputObjectType):
    field = graphene.String(required=True)
    value = graphene.String()
    operator = graphene.String(required=True)


class CreateEvidenceReplyInput(CommentInput, graphene.InputObjectType):
    evidence_id = graphene.String(required=True)
    comment_id = graphene.String(required=True)


class UpdatePopulationFieldType(graphene.InputObjectType):
    field = graphene.String(required=True)
    value = graphene.String()
    json_list = graphene.List(graphene.JSONString)


class UpdatePopulationInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    population_id = graphene.String(required=True)
    fields = graphene.List(UpdatePopulationFieldType, required=True)


class DeletePopulationDataFileInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    population_id = graphene.String(required=True)


class AddPopulationCompletenessAccuracyInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    population_id = graphene.String(required=True)
    files = graphene.List(types.InputFileType, required=True)


class UpdatePopulationCompletenessAccuracyInput(graphene.InputObjectType):
    id = graphene.ID(required=True)
    audit_id = graphene.String(required=True)
    population_id = graphene.String(required=True)
    new_name = graphene.String(required=True)


class DeletePopulationCompletenessAccuracyInput(graphene.InputObjectType):
    id = graphene.ID(required=True)
    audit_id = graphene.String(required=True)
    population_id = graphene.String(required=True)


class UploadPopulationFileInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    population_id = graphene.String(required=True)
    data_file = graphene.Field(types.InputFileType, required=True)


class PopulationDataFilterInput(graphene.InputObjectType):
    field = graphene.String(required=True)
    value = graphene.String(required=True)
    operator = graphene.String(required=True)
    type = graphene.String(required=True)


class DeleteAllEvidenceAttachmentInput(graphene.InputObjectType):
    evidence_ids = graphene.List(graphene.String, required=True)
    audit_id = graphene.String(required=True)


class AuditFeedbackInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    rate = graphene.Decimal(required=True)
    feedback = graphene.String()
    reason = graphene.JSONString()


class UpdateAuditorCriteriaFieldType(graphene.InputObjectType):
    field = graphene.String(required=True)
    value = graphene.String()
    boolean_value = graphene.Boolean()


class UpdateAuditorCriteriaInput(graphene.InputObjectType):
    criteria_id = graphene.ID(required=True)
    audit_id = graphene.String(required=True)
    fields = graphene.List(UpdateAuditorCriteriaFieldType, required=True)

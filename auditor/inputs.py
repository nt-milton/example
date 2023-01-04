import graphene

from population.inputs import PopulationInput


class AssignRequirementInput(graphene.InputObjectType):
    email = graphene.String(required=True)
    requirement_ids = graphene.List(graphene.String, required=True)
    audit_id = graphene.String(required=True)


class DeleteAuditEvidenceInput(graphene.InputObjectType):
    evidence_ids = graphene.List(graphene.String, required=True)
    audit_id = graphene.String(required=True)


class UpdateRequirementFieldInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    requirement_id = graphene.String(required=True)
    field = graphene.String(required=True)
    value = graphene.String(required=True)


class UpdateRequirementsStatusInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    ids = graphene.List(graphene.String, required=True)
    status = graphene.String(required=True)


class CreateRequirementTestInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    requirement_id = graphene.String(required=True)


class UpdateRequirementTestInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    requirement_id = graphene.String(required=True)
    test_id = graphene.String(required=True)
    field = graphene.String(required=True)
    value = graphene.String()


class AutomateRequirementTestInput(graphene.InputObjectType):
    test_id = graphene.String(required=True)
    requirement_id = graphene.String(required=True)
    audit_id = graphene.String(required=True)


class DeleteAuditorRequirementInput(graphene.InputObjectType):
    requirementIds = graphene.List(graphene.String, required=True)
    auditId = graphene.String(required=True)


class UpdateAuditorAuditDraftReportFileInput(graphene.InputObjectType):
    content = graphene.String(required=True)
    audit_id = graphene.String(required=True)


class UpdateAuditorAuditDraftReportInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)


class AddAuditorRequirementInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    name = graphene.String(required=True)
    related_evidence = graphene.List(graphene.String, required=True)
    related_criteria = graphene.List(graphene.String, required=True)
    language = graphene.String(required=True)


class UpdateAuditorRequirementInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    requirement_id = graphene.String(required=True)
    name = graphene.String(required=True)
    related_evidence = graphene.List(graphene.String, required=True)
    related_criteria = graphene.List(graphene.String, required=True)
    language = graphene.String(required=True)


class AddAuditorEvidenceRequestInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    name = graphene.String(required=True)
    related_requirements_ids = graphene.List(graphene.String, required=True)
    instructions = graphene.String(required=True)


class UpdateAuditorEvidenceRequestInput(AddAuditorEvidenceRequestInput):
    evidence_id = graphene.String(required=True)


class CreateAuditorPopulationSampleInput(PopulationInput):
    sample_size = graphene.Int(required=True)
    population_data_ids = graphene.List(graphene.String)


class UpdateAuditorAuditReportSectionInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    section = graphene.String(required=True)


class DeleteAuditorAuditPopulationInput(PopulationInput):
    sample_ids = graphene.List(graphene.String, required=True)


class UpdateDraftReportSectionContentInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    section = graphene.String(required=True)
    content = graphene.String(required=True)


class PublishAuditorReportVersionInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    version = graphene.String(required=True)
    report_publish_date = graphene.String()

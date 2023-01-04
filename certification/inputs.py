import graphene


class CertificationInput(graphene.InputObjectType):
    certification_id = graphene.String(required=True)
    is_unlocking = graphene.Boolean(required=True)


class UnlockedOrganizationCertificationInput(graphene.InputObjectType):
    organization_id = graphene.String(required=True)
    certifications = graphene.List(CertificationInput, required=True)


class UnlockedOrganizationCertificationAuditDatesInput(graphene.InputObjectType):
    organization_id = graphene.String(required=True)
    certification_id = graphene.String(required=True)
    target_audit_start_date = graphene.Date()
    target_audit_completion_date = graphene.Date()


class UnlockedCertificationCompletionDateInput(graphene.InputObjectType):
    organization_id = graphene.String(required=True)
    certification_id = graphene.String(required=True)
    target_audit_completion_date = graphene.Date()

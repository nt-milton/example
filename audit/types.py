import graphene
from graphene_django.types import DjangoObjectType

from audit.docusign_connection.docusign_connection import DocuSignConnection
from certification.types import LogoType
from coupon.models import Coupon
from laika.types import PaginationResponseType
from laika.utils.exceptions import ServiceException
from laika.utils.files import get_file_extension
from organization.types import OrganizationBaseType
from organization.utils.email_domain import get_email_domain_from_users
from user.models import Auditor
from user.types import UserType

from .constants import (
    AUDIT_FRAMEWORK_TYPES,
    AUDIT_TYPES,
    LEAD_AUDITOR_KEY,
    SOC_2_TYPE_1,
    SOC_2_TYPE_2,
    TRUSTED_CATEGORIES,
)
from .models import (
    TITLE_ROLES,
    Audit,
    AuditAuditor,
    AuditFeedback,
    AuditFeedbackReason,
    AuditFrameworkType,
    AuditReportSection,
    AuditStatus,
)
from .utils.audit import get_current_status, get_report_file


class AuditorType(graphene.ObjectType):
    class Meta:
        model = Auditor

    user = graphene.Field(UserType)
    audit_in_progress = graphene.Int()

    def resolve_user(self, info):
        return self.user

    def resolve_audit_in_progress(self, info):
        return (
            AuditAuditor.objects.filter(
                auditor=self, audit__completed_at__isnull=True
            ).count()
            or 0
        )


class AuditStatusType(graphene.ObjectType):
    class Meta:
        model = AuditStatus

    # audit status
    id = graphene.String()
    requested = graphene.Boolean()
    initiated = graphene.Boolean()
    fieldwork = graphene.Boolean()
    in_draft_report = graphene.Boolean()
    completed = graphene.Boolean()

    # initiated client
    engagement_letter_checked = graphene.Boolean()
    control_design_assessment_checked = graphene.Boolean()
    kickoff_meeting_checked = graphene.Boolean()

    # requested auditor
    confirm_audit_details = graphene.Boolean()
    engagement_letter_link = graphene.String()
    control_design_assessment_link = graphene.String()
    kickoff_meeting_link = graphene.String()
    confirm_audit_details_updated_at = graphene.String()
    engagement_letter_link_updated_at = graphene.String()
    control_design_assessment_link_updated_at = graphene.String()
    kickoff_meeting_link_updated_at = graphene.String()

    # initiated auditor
    confirm_engagement_letter_signed = graphene.Boolean()
    confirm_control_design_assessment = graphene.Boolean()
    confirm_kickoff_meeting = graphene.Boolean()
    kickoff_call_date = graphene.String()
    confirm_engagement_letter_signed_updated_at = graphene.String()
    confirm_control_design_assessment_updated_at = graphene.String()
    confirm_kickoff_meeting_updated_at = graphene.String()
    kickoff_call_date_updated_at = graphene.String()

    # fieldwork auditor
    representation_letter_link = graphene.String()
    management_assertion_link = graphene.String()
    subsequent_events_questionnaire_link = graphene.String()
    draft_report = graphene.String()
    draft_report_name = graphene.String()
    representation_letter_link_updated_at = graphene.String()
    management_assertion_link_updated_at = graphene.String()
    subsequent_events_questionnaire_link_updated_at = graphene.String()
    draft_report_updated_at = graphene.String()
    complete_fieldwork = graphene.Boolean()
    complete_fieldwork_updated_at = graphene.String()
    draft_report_generated = graphene.Boolean()
    draft_report_generated_updated_at = graphene.String()
    draft_report_file_generated = graphene.String()

    # draft report auditor
    confirm_completion_of_signed_documents = graphene.Boolean()
    final_report = graphene.String()
    confirm_completion_of_signed_documents_updated_at = graphene.String()
    final_report_updated_at = graphene.String()
    draft_report_approved = graphene.Boolean()
    draft_report_approved_timestamp = graphene.String()
    draft_report_approver_name = graphene.String()
    # client draft report status
    review_draft_report_checked = graphene.Boolean()
    representation_letter_checked = graphene.Boolean()
    management_assertion_checked = graphene.Boolean()
    subsequent_events_questionnaire_checked = graphene.Boolean()
    representation_letter_link = graphene.String()
    management_assertion_link = graphene.String()
    subsequent_events_questionnaire_link = graphene.String()

    current_status = graphene.String()

    representation_letter_link_status = graphene.String()
    management_assertion_link_status = graphene.String()
    subsequent_events_questionnaire_link_status = graphene.String()
    engagement_letter_link_status = graphene.String()
    control_design_assessment_link_status = graphene.String()

    def resolve_representation_letter_link_status(self: AuditStatus, info):
        docu_sign_connection = DocuSignConnection()
        email_domain = get_email_domain_from_users(self.audit.organization_id)
        status = docu_sign_connection.get_envelope_status(
            url=self.representation_letter_link, email_domain=email_domain
        )
        self.update_check_field(
            'representation_letter_checked',
            docu_sign_connection.is_envelope_completed(status),
        )
        return status

    def resolve_management_assertion_link_status(self: AuditStatus, info):
        docu_sign_connection = DocuSignConnection()
        email_domain = get_email_domain_from_users(self.audit.organization_id)
        status = docu_sign_connection.get_envelope_status(
            url=self.management_assertion_link, email_domain=email_domain
        )
        self.update_check_field(
            'management_assertion_checked',
            docu_sign_connection.is_envelope_completed(status),
        )
        return status

    def resolve_subsequent_events_questionnaire_link_status(self: AuditStatus, info):
        docu_sign_connection = DocuSignConnection()
        email_domain = get_email_domain_from_users(self.audit.organization_id)
        status = docu_sign_connection.get_envelope_status(
            url=self.subsequent_events_questionnaire_link, email_domain=email_domain
        )
        self.update_check_field(
            'subsequent_events_questionnaire_checked',
            docu_sign_connection.is_envelope_completed(status),
        )
        return status

    def resolve_engagement_letter_link_status(self: AuditStatus, info):
        docu_sign_connection = DocuSignConnection()
        email_domain = get_email_domain_from_users(self.audit.organization_id)
        status = docu_sign_connection.get_envelope_status(
            url=self.engagement_letter_link, email_domain=email_domain
        )
        self.update_check_field(
            'engagement_letter_checked',
            docu_sign_connection.is_envelope_completed(status),
        )
        return status

    def resolve_control_design_assessment_link_status(self: AuditStatus, info):
        docu_sign_connection = DocuSignConnection()
        email_domain = get_email_domain_from_users(self.audit.organization_id)
        status = docu_sign_connection.get_envelope_status(
            url=self.control_design_assessment_link, email_domain=email_domain
        )
        self.update_check_field(
            'control_design_assessment_checked',
            docu_sign_connection.is_envelope_completed(status),
        )
        return status

    def resolve_current_status(self, info):
        return get_current_status(audit_status=self)

    def resolve_draft_report_approver_name(self, info):
        approver = self.draft_report_approved_by
        return f'{approver.first_name} {approver.last_name}' if approver else None


class AuditFirmType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()


class FrameworkType(graphene.ObjectType):
    id = graphene.String()
    description = graphene.String()
    logo = graphene.Field(LogoType)
    type = graphene.String()


class AuditTypesType(graphene.ObjectType):
    id = graphene.String()
    organization_name = graphene.String()
    audit_id = graphene.String()
    type = graphene.String()
    audit_firm = graphene.Field(AuditFirmType)
    coupons = graphene.Int()
    configuration = graphene.JSONString()
    configuration_selected = graphene.JSONString()
    framework = graphene.Field(FrameworkType)
    feedback_reasons = graphene.List(graphene.String)

    def resolve_coupons(self, info):
        organization = info.context.user.organization
        coupon = Coupon.objects.filter(
            organization=organization, type=f'{self.type} {self.audit_firm.name}'
        ).first()
        return coupon.coupons if coupon else 0

    def resolve_id(self, info):
        return f'{self.type}_{self.audit_firm.name}_{self.audit_id}'

    def resolve_configuration(self, info):
        if self.framework.type == SOC_2_TYPE_1:
            return {'trust_services_categories': TRUSTED_CATEGORIES, 'as_of_date': True}

        if self.framework.type == SOC_2_TYPE_2:
            return {
                'trust_services_categories': TRUSTED_CATEGORIES,
                'report_period': True,
            }
        # TODO: This should be refactor once we work on the implementation
        #  for supporting other framework types
        #  https://heylaika.atlassian.net/browse/FZ-1656
        if self.framework.type != SOC_2_TYPE_1 or self.framework.type != SOC_2_TYPE_2:
            return {'trust_services_categories': TRUSTED_CATEGORIES, 'as_of_date': True}

    def resolve_configuration_selected(self, info):
        audit = Audit.objects.get(id=self.audit_id)
        return {
            'trust_services_categories': audit.audit_configuration[
                'trust_services_categories'
            ],
            'as_of_date': audit.audit_configuration['as_of_date'],
        }

    def resolve_feedback_reasons(self, info):
        return AuditFeedbackReason.objects.filter(
            audit_framework_type_id=self.framework.id
        ).values_list('reason', flat=True)


class DraftReportType(graphene.ObjectType):
    name = graphene.String(required=True)
    url = graphene.String()


class DraftReportSectionType(graphene.ObjectType):
    class Meta:
        model = AuditReportSection

    id = graphene.String()
    name = graphene.String()
    url = graphene.String()
    file_name = graphene.String()
    section = graphene.String()
    section_content = graphene.String()

    def resolve_section_content(self, info):
        return self.file.file.read().decode('UTF-8')


class AuditFeedbackType(graphene.ObjectType):
    id = graphene.String()
    rate = graphene.Decimal()
    feedback = graphene.String()
    reason = graphene.JSONString()
    user = graphene.Field(UserType)

    def resolve_id(self, info):
        return self.audit.id


class AuditType(graphene.ObjectType):
    class Meta:
        model = Audit

    id = graphene.String()
    name = graphene.String()
    audit_type = graphene.Field(AuditTypesType)
    completed_at = graphene.DateTime()
    created_at = graphene.DateTime()
    audit_firm = graphene.String()
    report_file_extension = graphene.String()
    status = graphene.Field(AuditStatusType)
    customer_success_manager = graphene.Field(UserType)
    compliance_architect = graphene.Field(UserType)
    auditor = graphene.Field(UserType)
    organization = graphene.String()
    auditor_list = graphene.List(AuditorType)
    auto_fetch_executed = graphene.Boolean()
    audit_configuration = graphene.JSONString()
    draft_report = graphene.Field(DraftReportType)
    draft_report_sections = graphene.List(DraftReportSectionType)
    use_new_version = graphene.Boolean()
    audit_organization = graphene.Field(OrganizationBaseType)
    feedback = graphene.Field(AuditFeedbackType)

    def resolve_auditor_list(self, info):
        return Auditor.objects.filter(audit_team__audit=self)

    def resolve_audit_type(self, info):
        audit = Audit.objects.get(id=self.id)
        framework = AuditFrameworkType.objects.get(id=audit.audit_framework_type.id)
        audit_framework_type_keys = dict(AUDIT_FRAMEWORK_TYPES)
        audit_type = audit_framework_type_keys[framework.audit_type]
        return AuditTypesType(
            audit_id=self.id,
            organization_name=self.organization.name,
            type=self.audit_type,
            audit_firm=AuditFirmType(name=self.audit_firm, id=self.id),
            framework=FrameworkType(
                id=framework.id,
                description=framework.description,
                logo=LogoType(
                    id=framework.certification.id, url=framework.certification.logo.url
                ),
                type=audit_type,
            ),
        )

    def resolve_status(self, info):
        audit_id = self.id
        audit_status = AuditStatus.objects.get(audit__id=audit_id)
        return audit_status

    def resolve_report_file_extension(self, info):
        audit_status = self.status.first()
        current_status = get_current_status(audit_status)

        file = get_report_file(audit=self, current_status=current_status)
        file_type = get_file_extension(str(file))

        return file_type

    def resolve_customer_success_manager(self, info):
        return self.organization.customer_success_manager_user

    def resolve_compliance_architect(self, info):
        return self.organization.compliance_architect_user

    def resolve_auditor(self, info):
        auditor_lead = AuditAuditor.objects.filter(
            audit_id=self.id, title_role=LEAD_AUDITOR_KEY
        ).first()
        if auditor_lead:
            return auditor_lead.auditor.user
        else:
            return None

    def resolve_auto_fetch_run(self, info):
        return self.auto_fetch_executed

    def resolve_audit_configuration(self, info):
        audit = Audit.objects.get(id=self.id)
        return {
            'trust_services_categories': audit.audit_configuration[
                'trust_services_categories'
            ],
            'as_of_date': audit.audit_configuration['as_of_date'],
        }

    def resolve_draft_report(self, info):
        audit = Audit.objects.get(id=self.id)

        audit_status = audit.status.first()
        draft_report = audit_status.draft_report

        if not draft_report:
            raise ServiceException("Uploaded Draft Report not found")

        return DraftReportType(name=draft_report.name, url=draft_report.url)

    def resolve_draft_report_sections(self, info):
        return [
            DraftReportSectionType(
                name=section.name,
                url=section.file.url,
                file_name=section.file.name,
                section=section.section,
            )
            for section in self.report_sections.order_by('section')
        ]

    def resolve_audit_organization(self, info):
        return self.organization

    def resolve_feedback(self, info):
        try:
            return self.audit_feedback
        except AuditFeedback.DoesNotExist:
            return None


class AuditResponseType(graphene.ObjectType):
    audits = graphene.List(AuditType)
    pagination = graphene.Field(PaginationResponseType)


audit_type_cert_mapper = {
    AUDIT_TYPES[0]: 'SOC 2 Type 1',
    AUDIT_TYPES[1]: 'SOC 2 Type 2',
}


class AuditorTeamType(graphene.ObjectType):
    id = graphene.String()
    user = graphene.Field(UserType)
    role = graphene.String()
    audit_in_progress = graphene.Int()

    def resolve_id(self, info):
        return self.user.id

    def resolve_audit_in_progress(self, info):
        return AuditAuditor.objects.filter(
            auditor__user=self.user, audit__completed_at__isnull=True
        ).count()

    def resolve_role(self, info):
        d = dict(TITLE_ROLES)
        return d[self.role]


class AuditAuditorsTeamType(graphene.ObjectType):
    id = graphene.String()
    auditors = graphene.List(AuditorTeamType)


class AuditorsResponseType(graphene.ObjectType):
    auditors = graphene.List(AuditorType)
    pagination = graphene.Field(PaginationResponseType)


class AuditAuditorType(DjangoObjectType):
    class Meta:
        model = AuditAuditor
        fields = ('id', 'audit', 'auditor', 'title_role')

    audit = graphene.Field(AuditType)
    auditor = graphene.Field(AuditorType)


class DraftReportFileResponseType(graphene.ObjectType):
    name = graphene.String(required=True)
    content = graphene.String()

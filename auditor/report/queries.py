import graphene

from audit.models import Audit, AuditReportSection, DraftReportComment
from audit.types import (
    DraftReportFileResponseType,
    DraftReportSectionType,
    DraftReportType,
)
from auditee.types import DraftReportCommentType
from auditor.utils import (
    is_auditor_associated_to_audit_firm,
    validate_auditor_get_draft_report_file,
)
from fieldwork.utils import get_draft_report_mentions_users
from laika.decorators import audit_service
from laika.utils.exceptions import ServiceException
from user.types import UserType


class ReportQuery(object):
    auditor_audit_draft_report_file = graphene.Field(
        DraftReportFileResponseType,
        audit_id=graphene.String(required=True),
    )

    auditor_audit_draft_report = graphene.Field(
        DraftReportType, audit_id=graphene.String(required=True)
    )

    auditor_draft_report_comments = graphene.List(
        DraftReportCommentType, audit_id=graphene.String(required=True)
    )

    auditor_draft_report_mentions_users = graphene.List(
        UserType, audit_id=graphene.String(required=True)
    )

    auditor_draft_report_section_content = graphene.Field(
        DraftReportSectionType,
        audit_id=graphene.String(required=True),
        section=graphene.String(required=True),
    )

    @audit_service(
        permission='audit.view_audit',
        exception_msg='Failed to get audit draft report section content.',
        revision_name='Get audit draft report section content',
    )
    def resolve_auditor_draft_report_section_content(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        audit = Audit.objects.get(id=audit_id)
        if not is_auditor_associated_to_audit_firm(
            audit=audit, auditor_id=info.context.user.id
        ):
            raise ServiceException("Auditor can not get draft report section content")

        return AuditReportSection.objects.get(
            audit_id=audit_id, section=kwargs.get('section')
        )

    @audit_service(
        permission='audit.view_audit',
        exception_msg='Failed to get audit draft report file.',
        revision_name='Get audit draft report file',
    )
    def resolve_auditor_audit_draft_report_file(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        audit = Audit.objects.get(id=audit_id)

        if not is_auditor_associated_to_audit_firm(
            audit=audit, auditor_id=info.context.user.id
        ):
            raise ServiceException("Auditor can not get draft report file")

        validate_auditor_get_draft_report_file(audit)

        audit_status = audit.status.first()
        draft_report_file = audit_status.draft_report_file_generated
        return DraftReportFileResponseType(
            name=draft_report_file.name,
            content=draft_report_file.file.read().decode('UTF-8'),
        )

    @audit_service(
        permission='audit.view_audit',
        exception_msg='Failed to get audit draft report.',
        revision_name='Get audit draft report',
    )
    def resolve_auditor_audit_draft_report(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        audit = Audit.objects.get(
            id=audit_id,
        )

        if not is_auditor_associated_to_audit_firm(
            audit=audit, auditor_id=info.context.user.id
        ):
            raise ServiceException("Auditor can not get draft report")

        audit_status = audit.status.first()
        draft_report = audit_status.draft_report

        if not draft_report:
            raise ServiceException("Uploaded Draft Report file not found")

        return DraftReportType(name=draft_report.name, url=draft_report.url)

    @audit_service(
        permission='audit.view_draftreportcomment',
        exception_msg='Failed to get draft report comments.',
        revision_name='Get auditor draft report comments',
    )
    def resolve_auditor_draft_report_comments(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        audit = Audit.objects.get(id=audit_id)
        auditor_id = info.context.user.id

        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=auditor_id):
            raise ServiceException(
                f'Auditor with id: {audit_id} can not get comments for audit {audit_id}'
            )
        return DraftReportComment.objects.filter(
            audit=audit,
            comment__is_deleted=False,
        ).order_by('page')

    @audit_service(
        permission='audit.view_draftreportcomment',
        exception_msg='Failed to get users for mentions in draft report',
        revision_name='Get mentions in draft report comments',
    )
    def resolve_auditor_draft_report_mentions_users(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        audit = Audit.objects.get(id=audit_id)
        auditor_id = info.context.user.id

        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=auditor_id):
            raise ServiceException(
                f'Auditor with id: {audit_id} can not '
                f'get users for mentions for audit {audit_id}'
            )

        return get_draft_report_mentions_users(audit)

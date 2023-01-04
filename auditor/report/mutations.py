import logging
from datetime import datetime
from multiprocessing.pool import ThreadPool

import graphene
from django.core.exceptions import PermissionDenied
from django.core.files import File

from alert.constants import ALERT_ACTIONS, ALERT_TYPES
from audit.inputs import (
    CreateDraftReportReplyInput,
    DeleteDraftReportReplyInput,
    UpdateDraftReportReplyInput,
)
from audit.models import Audit, AuditAuditor, AuditReportSection, DraftReportComment
from audit.sections_factory.sections_factory_client import SectionFactoryClient
from audit.types import AuditType
from auditee.inputs import UpdateDraftReportCommentStateInput
from auditee.types import DraftReportCommentType
from auditor.inputs import (
    PublishAuditorReportVersionInput,
    UpdateAuditorAuditDraftReportFileInput,
    UpdateAuditorAuditDraftReportInput,
    UpdateAuditorAuditReportSectionInput,
    UpdateDraftReportSectionContentInput,
)
from auditor.report.utils import alert_users_draft_report_published, publish_report
from auditor.utils import (
    is_auditor_associated_to_audit_firm,
    validate_auditor_get_draft_report_file,
)
from auditor.views import get_pdf_from_draft_report_html
from comment.models import Reply
from comment.types import BaseCommentType
from comment.utils import (
    delete_reply,
    strip_comment_reply_content,
    validate_comment_content,
)
from fieldwork.models import get_room_id_for_alerts
from fieldwork.utils import save_content_audit_draft_report_file
from laika.decorators import audit_service
from laika.settings import DJANGO_SETTINGS, NO_REPLY_EMAIL
from laika.utils.exceptions import ServiceException
from user.constants import AUDITOR_ADMIN

logger = logging.getLogger('auditor_report_mutation')
pool = ThreadPool()


class PublishAuditorReportVersion(graphene.Mutation):
    class Arguments:
        input = PublishAuditorReportVersionInput(required=True)

    success = graphene.Boolean()

    @audit_service(
        permission='audit.publish_draft_report',
        exception_msg='Failed to publish audit report',
        revision_name='Publish auditor report version',
    )
    def mutate(self, info, input):
        audit_id = input.get('audit_id')
        version = input.get('version')
        audit = Audit.objects.get(id=audit_id)
        report_publish_date = input.get('report_publish_date')
        if not is_auditor_associated_to_audit_firm(
            audit=audit, auditor_id=info.context.user.id
        ):
            raise ServiceException(f"Auditor can not publish {version} report")

        auditor_user = info.context.user
        logger.info(
            f'''Auditor user {auditor_user.email} published a new {version}
            report. Audit: {audit_id}'''
        )

        pool.apply_async(
            publish_report, args=(audit, version, auditor_user, report_publish_date)
        )

        return PublishAuditorReportVersion(success=True)


class UpdateAuditorAuditReportSection(graphene.Mutation):
    class Arguments:
        input = UpdateAuditorAuditReportSectionInput(required=True)

    audit = graphene.Field(AuditType)

    @audit_service(
        permission='audit.update_draft_report',
        exception_msg='Failed to refresh audit section',
        revision_name='Refresh audit section',
    )
    def mutate(self, info, input):
        audit_id = input.get('audit_id')
        section = input.get('section')

        user = info.context.user

        audit = Audit.objects.get(id=audit_id)
        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
            raise ServiceException("Auditor can not refresh section")

        audit_report_section = AuditReportSection.objects.get(
            audit__id=audit_id, section=section
        )

        factory_client = SectionFactoryClient(audit=audit)
        new_section_file = factory_client.generate_section(section=section)

        if new_section_file:
            audit_report_section.file = new_section_file['file']
            audit_report_section.save(update_fields=['file'])

        return UpdateAuditorAuditReportSection(audit=audit)


class UpdateAuditorAuditDraftReportFile(graphene.Mutation):
    class Arguments:
        input = UpdateAuditorAuditDraftReportFileInput(required=True)

    name = graphene.String()

    @audit_service(
        permission='audit.change_audit',
        exception_msg='Failed to update audit draft report file.',
        revision_name='Update audit draft report file ',
    )
    def mutate(self, info, input):
        audit_id = input.get('audit_id')
        content = input.get('content')

        audit = Audit.objects.get(id=audit_id)

        if not is_auditor_associated_to_audit_firm(
            audit=audit, auditor_id=info.context.user.id
        ):
            raise ServiceException("Auditor can not update draft report file")

        validate_auditor_get_draft_report_file(audit)

        new_file = save_content_audit_draft_report_file(
            audit=audit, organization=audit.organization, content=content
        )

        return UpdateAuditorAuditDraftReportFile(name=new_file.name)


class CreateAuditorDraftReportReply(graphene.Mutation):
    class Arguments:
        input = CreateDraftReportReplyInput(required=True)

    reply = graphene.Field(BaseCommentType)

    @audit_service(
        permission='audit.add_draftreportcomment',
        exception_msg='Failed to create draft report reply.',
        revision_name='Create draft report reply',
    )
    def mutate(self, info, input):
        audit = Audit.objects.get(id=input.get('audit_id'))
        user = info.context.user

        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
            raise ServiceException('Auditor can not create reply')

        draft_report_comment = DraftReportComment.objects.get(
            comment_id=input.comment_id, audit=audit
        )

        content = strip_comment_reply_content(input.get('content'))
        validate_comment_content(content=content, user_email=user.email)

        reply = Reply.objects.create(
            owner=info.context.user,
            content=content,
            parent=draft_report_comment.comment,
        )
        room_id = get_room_id_for_alerts(reply.parent.owner)
        mentions = reply.add_mentions(input.get('tagged_users'))
        hostname = DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')
        for mention in mentions:
            alert = mention.create_mention_alert(
                room_id=room_id, alert_type=ALERT_TYPES['AUDITEE_DRAFT_REPORT_MENTION']
            )
            template_context = {
                'draft_report_title': f'{audit.audit_type} Draft Report',
                'call_to_action_url': (
                    f'{hostname}/audits/{audit.id}?activeKey=Draft%20Report'
                ),
                'alert_action': ALERT_ACTIONS['AUDITEE_DRAFT_REPORT_MENTION'],
                'audit_name': audit.name,
            }
            context = {
                'subject': (
                    f'{alert.sender.get_full_name()} mentioned you '
                    f'in your {audit.name} Draft Report'
                ),
                'from_email': NO_REPLY_EMAIL,
                'to': alert.receiver.email,
                'template': 'alert_draft_report_new_mentions.html',
                'template_context': template_context,
            }
            mention.send_mention_email(context)

        return CreateAuditorDraftReportReply(reply)


class UpdateAuditorDraftReportReply(graphene.Mutation):
    class Arguments:
        input = UpdateDraftReportReplyInput(required=True)

    reply = graphene.Field(BaseCommentType)

    @audit_service(
        permission='audit.change_draftreportcomment',
        exception_msg='Failed to update draft report reply.',
        revision_name='Update draft report reply',
    )
    def mutate(self, info, input):
        reply_id = input.get('reply_id')
        audit_id = input.get('audit_id')
        user = info.context.user

        audit = Audit.objects.get(id=audit_id)
        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
            raise ServiceException('Auditor can not update reply')

        try:
            reply = Reply.objects.get(id=reply_id, parent_id=input.get('comment_id'))
            if not reply.is_reply_owner(user):
                raise PermissionDenied

            validate_comment_content(
                content=input.get('content'), user_email=user.email
            )

            reply.update(input)

        except Reply.DoesNotExist:
            logger.warning(
                f'Reply with id: {reply_id} does not exist User: {user.email}'
            )

        return UpdateAuditorDraftReportReply(reply)


class DeleteAuditorDraftReportReply(graphene.Mutation):
    class Arguments:
        input = DeleteDraftReportReplyInput(required=True)

    reply = graphene.Field(BaseCommentType)

    @audit_service(
        permission='audit.delete_draftreportcomment',
        exception_msg='Failed to delete draft report reply.',
        revision_name='Delete draft report reply',
    )
    def mutate(self, info, input):
        reply_id = input.get('reply_id')
        audit_id = input.get('audit_id')

        audit = Audit.objects.get(id=audit_id)

        user = info.context.user

        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
            raise ServiceException(
                f'Auditor with email: {user.email} can not '
                f'delete comments for audit {audit_id}'
            )
        try:
            reply = delete_reply(user=user, reply_input=input)
        except Reply.DoesNotExist:
            logger.warning(
                f'Reply with id: {reply_id} does not exist User: {user.email}'
            )

        return DeleteAuditorDraftReportReply(reply)


class UpdateAuditorAuditDraftReport(graphene.Mutation):
    class Arguments:
        input = UpdateAuditorAuditDraftReportInput(required=True)

    audit = graphene.Field(AuditType)

    @audit_service(
        permission='audit.publish_draft_report',
        exception_msg='Failed to publish audit draft report.',
        revision_name='Publish audit draft report ',
    )
    def mutate(self, info, input):
        audit_id = input.get('audit_id')
        audit = Audit.objects.get(id=input.audit_id)

        if not is_auditor_associated_to_audit_firm(
            audit=audit, auditor_id=info.context.user.id
        ):
            raise ServiceException("Auditor can not publish draft report")

        validate_auditor_get_draft_report_file(audit)

        audit_status = audit.status.first()
        draft_report_file = audit_status.draft_report_file_generated
        draft_report_html = draft_report_file.file.read().decode('UTF-8')
        draft_report_pdf = get_pdf_from_draft_report_html(audit, draft_report_html)

        organization_name = audit.organization.name
        audit_type = audit.audit_type
        draft_report_name = f'Draft - {organization_name} - {audit_type}.pdf'
        audit_status.draft_report_name = draft_report_name
        audit_status.draft_report = File(name=draft_report_name, file=draft_report_pdf)
        audit_status.draft_report_updated_at = datetime.now()
        audit_status.save()

        auditor_user = info.context.user
        logger.info(
            f'''Auditor user {auditor_user.email} published a new draft
            report. Audit: {audit_id}'''
        )

        alert_users_draft_report_published(audit, auditor_user)

        return UpdateAuditorAuditDraftReport(audit=audit)


class UpdateAuditorDraftReportSectionContent(graphene.Mutation):
    class Arguments:
        input = UpdateDraftReportSectionContentInput(required=True)

    name = graphene.String()

    @audit_service(
        permission='audit.update_draft_report',
        exception_msg='Failed to update draft report section content.',
        revision_name='Update audit draft report section content ',
    )
    def mutate(self, info, input):
        audit_id = input.get('audit_id')
        content = input.get('content')
        section = input.get('section')

        audit = Audit.objects.get(id=audit_id)

        if not is_auditor_associated_to_audit_firm(
            audit=audit, auditor_id=info.context.user.id
        ):
            raise ServiceException(
                "Auditor can not update draft report section content"
            )

        draft_report_section = AuditReportSection.objects.get(
            audit_id=audit_id, section=section
        )

        draft_report_section.save_draft_report_content(content=content, section=section)

        return UpdateAuditorDraftReportSectionContent(name=draft_report_section.name)


class UpdateAuditorDraftReportCommentState(graphene.Mutation):
    class Arguments:
        input = UpdateDraftReportCommentStateInput(required=True)

    draft_report_comment = graphene.Field(DraftReportCommentType)

    @audit_service(
        permission='audit.change_draftreportcomment',
        exception_msg='Failed to update draft report comment state.',
        revision_name='Update draft report comment state',
    )
    def mutate(self, info, input):
        audit = Audit.objects.get(id=input.get('audit_id'))
        user = info.context.user

        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
            raise ServiceException('Auditor can not update draft report comment state')

        is_lead_auditor_or_admin = (
            AuditAuditor.objects.filter(
                title_role__in=['lead_auditor'],
                audit=audit,
                auditor__user__email=user.email,
            ).exists()
            or user.role == AUDITOR_ADMIN
        )

        if not is_lead_auditor_or_admin:
            raise ServiceException('Auditor can not update draft report comment state')

        draft_report_comment = DraftReportComment.objects.get(
            comment_id=input.comment_id, audit=audit
        )

        updated_comment = draft_report_comment.update(user, input)
        return UpdateAuditorDraftReportCommentState(updated_comment)


class ReportMutation(object):
    update_auditor_audit_report_section = UpdateAuditorAuditReportSection.Field()
    update_auditor_audit_draft_report_file = UpdateAuditorAuditDraftReportFile.Field()
    publish_auditor_report_version = PublishAuditorReportVersion.Field()

    create_auditor_draft_report_reply = CreateAuditorDraftReportReply.Field()
    update_auditor_draft_report_reply = UpdateAuditorDraftReportReply.Field()
    delete_auditor_draft_report_reply = DeleteAuditorDraftReportReply.Field()
    update_auditor_audit_draft_report = UpdateAuditorAuditDraftReport.Field()
    update_auditor_draft_report_comment_state = (
        UpdateAuditorDraftReportCommentState.Field()
    )

    update_auditor_draft_report_section_content = (
        UpdateAuditorDraftReportSectionContent.Field()
    )

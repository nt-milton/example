import logging
from datetime import datetime

import graphene
from django.core.exceptions import PermissionDenied

from alert.constants import ALERT_TYPES
from audit.inputs import ApproveAuditeeDraftReportInput
from audit.models import (
    Audit,
    AuditAlert,
    AuditFeedback,
    AuditStatus,
    DraftReportComment,
)
from audit.types import AuditFeedbackType, AuditStatusType
from audit.utils.tags import link_audit_tags_to_action_items_evidence
from auditee.inputs import (
    CreateNotificationReviewedDraftReportInput,
    RunFetchEvidenceInput,
)
from fieldwork.constants import (
    ALLOW_ROLES_TO_ASSIGN_USER,
    ATTACH_FLAGGED_MONITORS_ERROR,
    DOCUMENT_FETCH_TYPE,
    ER_STATUS_DICT,
    MONITOR_FETCH_TYPE,
    OBJECT_FETCH_TYPE,
    OFFICER_FETCH_TYPE,
    POLICY_FETCH_TYPE,
    TEAM_FETCH_TYPE,
    TRAINING_FETCH_TYPE,
    VENDOR_FETCH_TYPE,
)
from fieldwork.inputs import (
    AddEvidenceAttachmentInput,
    AssignEvidenceInput,
    AuditFeedbackInput,
    DeleteAllEvidenceAttachmentInput,
    DeleteEvidenceAttachmentInput,
    RenameAttachmentInput,
    UpdateEvidenceInput,
    UpdateEvidenceLaikaReviewedInput,
    UpdateEvidenceStatusInput,
)
from fieldwork.models import (
    Attachment,
    EVFetchLogicFilter,
    Evidence,
    EvidenceStatusTransition,
)
from fieldwork.types import FieldworkEvidenceType
from fieldwork.util.evidence_attachment import delete_all_evidence_attachments
from fieldwork.util.evidence_request import (
    calculate_er_times_move_back_to_open,
    update_attachments_status,
)
from fieldwork.utils import (
    add_attachment,
    assign_evidence_user,
    bulk_laika_review_evidence,
    get_display_id_order_annotation,
    update_evidence_status,
)
from laika.aws.ses import send_email
from laika.decorators import laika_service
from laika.settings import DJANGO_SETTINGS, NO_REPLY_EMAIL
from laika.types import ErrorType
from laika.utils.exceptions import GENERIC_FILES_ERROR_MSG, ServiceException
from monitor.models import MonitorInstanceStatus, OrganizationMonitor
from user.constants import ROLE_ADMIN, ROLE_SUPER_ADMIN
from user.models import User

from .types import DraftReportCommentType
from .utils import (
    create_tmp_attachments_for_fk_types,
    delete_audit_tmp_attachments,
    get_draft_report_alert_and_email_receivers,
    get_er_metrics_for_fetch,
    get_results_from_query,
    laika_review_evidence,
    run_fetch_for_other_types,
    update_description_for_evs,
    update_fetch_accuracy_for_evs,
    update_metrics_for_fetch,
)

logger = logging.getLogger('auditee_mutations')

DELETE_ATTCH_ERROR_MSG = 'Delete cannot be applied after ERs are Laika Reviewed'


class UpdateAuditeeEvidenceLaikaReviewed(graphene.Mutation):
    class Arguments:
        input = UpdateEvidenceLaikaReviewedInput(required=True)

    ids = graphene.List(graphene.String)

    @laika_service(
        permission='fieldwork.review_evidence',
        exception_msg='Failed to update laika reviewed.',
        revision_name='Update evidence laika reviewed',
    )
    def mutate(self, info, input):
        organization = info.context.user.organization
        ids = laika_review_evidence(input, organization)
        return UpdateAuditeeEvidenceLaikaReviewed(ids)


class AssignAuditeeEvidence(graphene.Mutation):
    class Arguments:
        input = AssignEvidenceInput(required=True)

    ids = graphene.List(graphene.String)

    @laika_service(
        permission='fieldwork.assign_evidence',
        exception_msg='Failed to assign auditee evidence.',
        revision_name='Update auditee evidence assignee',
    )
    def mutate(self, info, input):
        organization = info.context.user.organization
        ids = assign_evidence_user(input, organization)
        return AssignAuditeeEvidence(ids)


class RunFetchEvidence(graphene.Mutation):
    class Arguments:
        input = RunFetchEvidenceInput(required=True)

    audit_id = graphene.String(default_value=True)
    monitors_error = graphene.Field(ErrorType)

    @laika_service(
        permission='fieldwork.fetch_evidence_attachment',
        exception_msg='Failed to fetch evidence logic.',
        revision_name='Get fieldwork fetch logic.',
    )
    def mutate(self, info, input):
        organization = info.context.user.organization
        audit = Audit.objects.get(pk=input.audit_id, organization=organization)
        timezone = input.get('timezone')
        evidence = Evidence.objects.filter(audit_id=audit.id)
        if input.get('evidence_ids'):
            evidence = evidence.filter(id__in=input.get('evidence_ids'))

        logger.info(f'--- Run fetch evidence for audit {audit.id} ---')

        if any(ev.is_laika_reviewed for ev in evidence):
            logger.warning('Fieldwork Fetch - Normal alert')
            raise ServiceException('Fetch cannot be run after ERs are Laika Reviewed')

        ev_fetch_logic_filters = []
        fk_fetch_types = {
            POLICY_FETCH_TYPE: [],
            DOCUMENT_FETCH_TYPE: [],
            TRAINING_FETCH_TYPE: [],
            TEAM_FETCH_TYPE: [],
        }

        other_fetch_types = [
            OBJECT_FETCH_TYPE,
            VENDOR_FETCH_TYPE,
            OFFICER_FETCH_TYPE,
            MONITOR_FETCH_TYPE,
        ]
        flagged_monitors_exist = False
        link_audit_tags_to_action_items_evidence(organization)
        for ev_request in evidence:
            metrics = get_er_metrics_for_fetch(ev_request)

            fetch_logics = (
                ev_request.fetch_logic.all()
                .annotate(
                    code_sort=get_display_id_order_annotation(
                        preffix='FL-', field='code'
                    )
                )
                .order_by('-code_sort')
            )
            for i, fl in enumerate(fetch_logics):
                metrics = update_metrics_for_fetch(ev_request, metrics, i)
                res, query = get_results_from_query(organization, fl)
                if any(fetch_type in fl.type for fetch_type in other_fetch_types):
                    flagged_monitors_exist = run_fetch_for_other_types(
                        organization, ev_request, fl, res, query, timezone, metrics
                    )

                if fl.type in fk_fetch_types:
                    # Save results for the same type in one array so
                    # the creation of files (policies, docs, team logs)is done
                    # only once for the same result
                    fk_fetch_types[fl.type].extend(res)
                    ev_fetch_logic_filters.append(
                        EVFetchLogicFilter(
                            organization=organization,
                            evidence=ev_request,
                            results=res,
                            fetch_logic=fl,
                        )
                    )

        create_tmp_attachments_for_fk_types(
            organization, audit, fk_fetch_types, timezone
        )

        for ev_fetch_logic in ev_fetch_logic_filters:
            ev_fetch_logic.run_filter_query()

        update_fetch_accuracy_for_evs(evidence)
        update_description_for_evs(evidence)

        if not audit.auto_fetch_executed:
            audit.auto_fetch_executed = True
            audit.save(update_fields=["auto_fetch_executed"])

        monitors_error = (
            ATTACH_FLAGGED_MONITORS_ERROR if flagged_monitors_exist else None
        )

        delete_audit_tmp_attachments(audit)

        return RunFetchEvidence(audit_id=audit.id, monitors_error=monitors_error)


class UpdateAuditeeEvidenceStatus(graphene.Mutation):
    class Arguments:
        input = UpdateEvidenceStatusInput(required=True)

    updated = graphene.List(graphene.String)

    @laika_service(
        permission='fieldwork.change_evidence',
        exception_msg='Failed to change evidences status',
        revision_name='Change evidences status',
    )
    def mutate(self, info, input):
        user = info.context.user
        organization = user.organization
        status = input.get('status')
        audit = Audit.objects.get(id=input.get('audit_id'), organization=organization)
        evidence = Evidence.objects.filter(id__in=input.get('ids'), audit=audit)
        updated_evidence = update_evidence_status(
            evidence, status, transitioned_by=user
        )

        Evidence.objects.bulk_update(
            updated_evidence,
            ['status', 'is_laika_reviewed', 'times_moved_back_to_open'],
        )

        # TODO: Refactor on FZ-2548
        if status == 'open':
            updated_evidence = bulk_laika_review_evidence(evidence, back_to_open=True)

            Evidence.objects.bulk_update(updated_evidence, ['is_laika_reviewed'])

        return UpdateAuditeeEvidenceStatus(updated=input.get('ids'))


class AddAuditeeEvidenceAttachment(graphene.Mutation):
    class Arguments:
        input = AddEvidenceAttachmentInput(required=True)

    document_ids = graphene.List(graphene.Int)
    monitors_error = graphene.Field(ErrorType)

    @laika_service(
        permission='fieldwork.change_evidence',
        exception_msg=GENERIC_FILES_ERROR_MSG,
        revision_name='Add attachment to evidence',
        atomic=True,
    )
    def mutate(self, info, input):
        fieldwork_evidence = Evidence.objects.get(id=input.id)

        if fieldwork_evidence.status != ER_STATUS_DICT['Open']:
            raise ServiceException('Evidence request should be open')

        ids = add_attachment(
            organization=info.context.user.organization,
            fieldwork_evidence=fieldwork_evidence,
            input=input,
        )
        monitors = input.get('monitors', [])
        uploaded_monitor_ids = [monitor.id for monitor in monitors]
        flagged_monitors_exist = OrganizationMonitor.objects.filter(
            organization=info.context.user.organization,
            id__in=uploaded_monitor_ids,
            status=MonitorInstanceStatus.TRIGGERED,
        ).exists()

        monitors_error = (
            ATTACH_FLAGGED_MONITORS_ERROR if flagged_monitors_exist else None
        )

        return AddAuditeeEvidenceAttachment(
            document_ids=ids, monitors_error=monitors_error
        )


class DeleteAuditeeEvidenceAttachment(graphene.Mutation):
    class Arguments:
        input = DeleteEvidenceAttachmentInput(required=True)

    attachment_id = graphene.String()

    @laika_service(
        permission='fieldwork.delete_evidence_attachment',
        exception_msg='Failed to delete evidence attachment',
        revision_name='Delete evidence attachment',
        atomic=True,
    )
    def mutate(self, info, **kwargs):
        attachment_id = kwargs['input'].get('attachment_id')
        evidence_id = kwargs['input'].get('evidence_id')
        audit_id = kwargs['input'].get('audit_id')
        attachment = Attachment.objects.get(
            id=attachment_id, evidence_id=evidence_id, evidence__audit_id=audit_id
        )

        if attachment.evidence.is_laika_reviewed:
            raise ServiceException(DELETE_ATTCH_ERROR_MSG)

        if attachment.has_been_submitted:
            raise ServiceException('Only Open attachments can be deleted')
        attachment.is_deleted = True
        attachment.deleted_by = info.context.user
        attachment.save()
        return DeleteAuditeeEvidenceAttachment(attachment_id=attachment_id)


class UpdateAuditeeEvidence(graphene.Mutation):
    class Arguments:
        input = UpdateEvidenceInput(required=True)

    updated = graphene.String()

    @laika_service(
        permission='fieldwork.change_evidence',
        exception_msg='Failed to update evidence',
        revision_name='Update customer evidence',
    )
    def mutate(self, info, input):
        evidence = Evidence.objects.get(id=input.get('evidence_id'))
        new_status = input.get('status')
        current_laika_review_value = evidence.is_laika_reviewed
        if new_status == 'open':
            evidence.is_laika_reviewed = False
            evidence.times_moved_back_to_open = calculate_er_times_move_back_to_open(
                evidence
            )

        user_role = info.context.user.role
        if new_status == ER_STATUS_DICT['Submitted'] and user_role == ROLE_SUPER_ADMIN:
            evidence.is_laika_reviewed = True

        if 'assignee_email' in input:
            if not input.get('assignee_email'):
                assignee = None
            else:
                assignee = User.objects.get(email=input.get('assignee_email'))

                if assignee.role not in ALLOW_ROLES_TO_ASSIGN_USER:
                    raise ServiceException(
                        f'Only roles {ALLOW_ROLES_TO_ASSIGN_USER}'
                        'can assign a user to an evidence'
                    )
            evidence.assignee = assignee

        if new_status:
            update_attachments_status(new_status, evidence.attachments)
            from_status = evidence.status
            EvidenceStatusTransition.objects.create(
                evidence=evidence,
                from_status=from_status,
                to_status=new_status,
                laika_reviewed=current_laika_review_value,
                transitioned_by=info.context.user,
            )

        updated_evidence = input.to_model(update=evidence)

        return UpdateAuditeeEvidence(updated=updated_evidence.id)


class RenameAuditeeAttachment(graphene.Mutation):
    class Arguments:
        input = RenameAttachmentInput(required=True)

    updated = graphene.String()

    @laika_service(
        permission='fieldwork.change_evidence',
        exception_msg='Failed to rename evidence attachment',
        revision_name='Rename customer evidence attachment',
    )
    def mutate(self, info, input):
        attachment = Attachment.objects.get(
            id=input.attachment_id,
            evidence_id=input.evidence_id,
        )
        attachment.rename(input)

        return RenameAuditeeAttachment(updated=attachment.id)


class ApproveAuditeeDraftReport(graphene.Mutation):
    class Arguments:
        input = ApproveAuditeeDraftReportInput(required=True)

    audit_status = graphene.Field(AuditStatusType)

    @laika_service(
        permission='audit.change_audit',
        exception_msg='Failed to approve audit draft report.',
        revision_name='Approve audit draft report',
    )
    def mutate(self, info, input):
        user = info.context.user
        organization = user.organization
        audit = Audit.objects.get(id=input.audit_id, organization=organization)

        if user.role != ROLE_ADMIN:
            raise PermissionDenied

        audit_status = AuditStatus.objects.get(
            audit__id=audit.id, audit__organization__id=organization.id
        )
        audit_status.draft_report_approved = True
        audit_status.draft_report_approved_timestamp = datetime.now()
        audit_status.draft_report_approved_by = user

        audit_status.save()
        alert_receivers = get_draft_report_alert_and_email_receivers(audit.id)
        hostname = DJANGO_SETTINGS.get('LAIKA_AUDIT_REDIRECT')
        template_context = {
            'status_title': (
                f'{organization} approved the draft report for '
                f'their {audit.audit_type} audit.'
            ),
            'status_description': (
                'Log in to provide the reporting '
                'documentation and begin finalizing the '
                'report.'
            ),
            'call_to_action_url': (
                f'{hostname}/audits/{audit.id}?activeKey='
                'Report%20Creation_Draft%20Report&isSubmenu'
                '=true'
            ),
            'status_cta': 'VIEW AUDIT',
        }
        for receiver in alert_receivers:
            AuditAlert.objects.custom_create(
                audit=audit,
                sender=user,
                receiver=receiver.user,
                alert_type=ALERT_TYPES['ORG_APPROVED_DRAFT_REPORT'],
            )
            send_email(
                subject=f'{organization} approved the draft report',
                from_email=NO_REPLY_EMAIL,
                to=[receiver.user.email],
                template='alert_draft_report_status.html',
                template_context=template_context,
            )

        return ApproveAuditeeDraftReport(audit_status=audit_status)


class CreateAuditeeNotificationReviewedDraftReport(graphene.Mutation):
    class Arguments:
        input = CreateNotificationReviewedDraftReportInput(required=True)

    draft_report_comments = graphene.List(DraftReportCommentType)

    @laika_service(
        permission='audit.change_draftreportcomment',
        exception_msg='Failed to notify review draft report.',
        revision_name='Notify draft report review.',
    )
    def mutate(self, info, input):
        user = info.context.user
        logger.info(
            f'User {user.email} is notifying auditor to review draft report comments.'
        )

        organization = info.context.user.organization
        audit = Audit.objects.get(
            id=input.audit_id, organization=info.context.user.organization
        )
        alert_receivers = get_draft_report_alert_and_email_receivers(audit.id)

        hostname = DJANGO_SETTINGS.get('LAIKA_AUDIT_REDIRECT')
        template_context = {
            'status_title': (
                f'Suggested edits for {organization}\'s '
                f'{audit.audit_type} report are ready for review.'
            ),
            'status_description': 'Log in to review suggestions.',
            'call_to_action_url': (
                f'{hostname}/audits/{audit.id}?activeKey='
                'Report%20Creation_Draft%20Report&isSubmenu'
                '=true'
            ),
            'status_cta': 'REVIEW SUGGESTIONS',
        }
        for receiver in alert_receivers:
            AuditAlert.objects.custom_create(
                audit=audit,
                sender=user,
                receiver=receiver.user,
                alert_type=ALERT_TYPES['ORG_SUGGESTED_DRAFT_EDITS'],
            )

            send_email(
                subject=f'Review {organization}\'s suggested edits',
                from_email=NO_REPLY_EMAIL,
                to=[receiver.user.email],
                template='alert_draft_report_status.html',
                template_context=template_context,
            )

        draft_report_comments = DraftReportComment.objects.filter(
            audit=audit, auditor_notified=False
        )
        for dr_comment in draft_report_comments:
            dr_comment.auditor_notified = True
        DraftReportComment.objects.bulk_update(
            draft_report_comments, ['auditor_notified']
        )

        return CreateAuditeeNotificationReviewedDraftReport(draft_report_comments)


class DeleteAuditeeAllEvidenceAttachments(graphene.Mutation):
    class Arguments:
        input = DeleteAllEvidenceAttachmentInput(required=True)

    evidence = graphene.List(FieldworkEvidenceType)

    @laika_service(
        permission='fieldwork.delete_evidence_attachment',
        exception_msg='Failed to delete evidence attachments',
        revision_name='Delete all evidence attachments',
        atomic=True,
    )
    def mutate(self, info, input):
        laika_reviewed_er_exists = Evidence.objects.filter(
            id__in=input.evidence_ids, audit__id=input.audit_id, is_laika_reviewed=True
        ).exists()

        if laika_reviewed_er_exists:
            raise ServiceException(DELETE_ATTCH_ERROR_MSG)
        deleted_by = info.context.user
        evidence = delete_all_evidence_attachments(
            input.audit_id, input.evidence_ids, deleted_by, ER_STATUS_DICT['Open']
        )
        return DeleteAuditeeAllEvidenceAttachments(evidence=evidence)


class AddAuditeeAuditFeedback(graphene.Mutation):
    class Arguments:
        input = AuditFeedbackInput(required=True)

    feedback = graphene.Field(AuditFeedbackType)

    @laika_service(
        permission='audit.add_auditfeedback',
        exception_msg='Failed to add audit feedback.',
        revision_name='Add audit feedback.',
    )
    def mutate(self, info, input):
        user = info.context.user
        organization = user.organization
        audit = Audit.objects.get(id=input.audit_id, organization=organization)

        audit_feedback, _ = AuditFeedback.objects.update_or_create(
            audit=audit,
            defaults={
                'rate': input.rate,
                'feedback': input.feedback,
                'reason': input.reason,
                'user': user,
            },
        )

        return AddAuditeeAuditFeedback(feedback=audit_feedback)

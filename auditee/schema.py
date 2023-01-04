import graphene
from django.db.models import Q

from audit.models import Audit, DraftReportComment
from audit.types import DraftReportType
from auditee.utils import user_in_audit_organization
from drive.models import DriveEvidence
from drive.schema import filter_drive_evidence
from fieldwork.constants import DEFAULT_PAGE_SIZE
from fieldwork.inputs import EvidenceFilterInput
from fieldwork.models import Evidence
from fieldwork.types import (
    AcceptedEvidenceCountType,
    EvidenceCommentType,
    FieldworkDocumentsResponseType,
    FieldworkEvidenceAllResponseType,
    FieldworkEvidenceResponseType,
    FieldworkEvidenceType,
    LaikaReviewedEvidenceCountType,
    evidence_comment_pools_enum,
    evidence_status_enum,
)
from fieldwork.utils import (
    get_assignees_for_evidence,
    get_comment_mention_users_by_pool,
    get_draft_report_mentions_users,
    get_evidence_by_args,
    get_evidence_by_audit,
    get_tags_and_categories_info,
    map_attachments_to_drive_evidence_type,
    map_documents_to_evidence_req_attachment,
    map_policies_to_evidence_req_attachment,
)
from laika.decorators import laika_service
from laika.types import OrderInputType, PaginationInputType
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.exceptions import ServiceException
from laika.utils.paginator import get_paginated_result
from population.models import AuditPopulation
from user.types import UserType

from .mutations import (
    AddAuditeeAuditFeedback,
    AddAuditeeEvidenceAttachment,
    ApproveAuditeeDraftReport,
    AssignAuditeeEvidence,
    CreateAuditeeNotificationReviewedDraftReport,
    DeleteAuditeeAllEvidenceAttachments,
    DeleteAuditeeEvidenceAttachment,
    RenameAuditeeAttachment,
    RunFetchEvidence,
    UpdateAuditeeEvidence,
    UpdateAuditeeEvidenceLaikaReviewed,
    UpdateAuditeeEvidenceStatus,
)
from .population.mutations import PopulationMutation
from .population.queries import PopulationQuery
from .types import DraftReportCommentType


class Mutation(PopulationMutation, object):
    update_auditee_evidence_laika_reviewed = UpdateAuditeeEvidenceLaikaReviewed.Field()
    assign_auditee_evidence = AssignAuditeeEvidence.Field()
    run_fetch_evidence = RunFetchEvidence.Field()
    update_auditee_evidence_status = UpdateAuditeeEvidenceStatus.Field()
    add_auditee_evidence_attachment = AddAuditeeEvidenceAttachment.Field()
    delete_auditee_evidence_attachment = DeleteAuditeeEvidenceAttachment.Field()
    delete_auditee_all_evidence_attachments = (
        DeleteAuditeeAllEvidenceAttachments.Field()
    )
    update_auditee_evidence = UpdateAuditeeEvidence.Field()
    rename_auditee_attachment = RenameAuditeeAttachment.Field()
    approve_auditee_draft_report = ApproveAuditeeDraftReport.Field()
    create_auditee_notification_reviewed_draft_report = (
        CreateAuditeeNotificationReviewedDraftReport.Field()
    )
    add_auditee_audit_feedback = AddAuditeeAuditFeedback.Field()


class Query(PopulationQuery, object):
    auditee_all_evidence = graphene.Field(
        FieldworkEvidenceAllResponseType,
        audit_id=graphene.String(required=True),
        status=graphene.Argument(evidence_status_enum),
        order_by=graphene.Argument(OrderInputType, required=False),
        filter=graphene.List(EvidenceFilterInput, required=False),
    )
    auditee_accepted_evidence_count = graphene.Field(
        AcceptedEvidenceCountType, audit_id=graphene.String(required=True)
    )
    auditee_reviewed_evidence_count = graphene.Field(
        LaikaReviewedEvidenceCountType, audit_id=graphene.String(required=True)
    )
    auditee_evidence = graphene.Field(
        FieldworkEvidenceType,
        evidence_id=graphene.String(required=True),
        audit_id=graphene.String(required=True),
        is_evidence_detail=graphene.Boolean(),
    )
    auditee_assignees_for_evidence = graphene.List(
        UserType, audit_id=graphene.String(required=True)
    )
    auditee_evidence_comment_users = graphene.List(
        UserType,
        audit_id=graphene.String(required=True),
        pool=graphene.Argument(evidence_comment_pools_enum, required=True),
    )

    auditee_documents = graphene.Field(
        FieldworkDocumentsResponseType,
        audit_id=graphene.String(required=True),
        order_by=graphene.Argument(OrderInputType, required=False),
        pagination=graphene.Argument(PaginationInputType, required=False),
        search_criteria=graphene.String(required=False),
        categories_filters=graphene.List(graphene.String, required=False),
        framework_filter=graphene.String(required=False),
    )

    auditee_evidence_list = graphene.Field(
        FieldworkEvidenceResponseType,
        audit_id=graphene.String(required=True),
        status=graphene.Argument(evidence_status_enum),
        pagination=graphene.Argument(PaginationInputType, required=False),
        order_by=graphene.Argument(OrderInputType, required=False),
        filter=graphene.List(EvidenceFilterInput, required=False),
        search_criteria=graphene.String(required=False),
    )

    auditee_evidence_comments = graphene.List(
        EvidenceCommentType,
        audit_id=graphene.String(required=True),
        evidence_id=graphene.String(required=True),
        pool=graphene.Argument(evidence_comment_pools_enum, required=True),
    )

    auditee_audit_draft_report = graphene.Field(
        DraftReportType, audit_id=graphene.String(required=True)
    )

    auditee_draft_report_comments = graphene.List(
        DraftReportCommentType, audit_id=graphene.String(required=True)
    )

    auditee_draft_report_mentions_users = graphene.List(
        UserType, audit_id=graphene.String(required=True)
    )

    @laika_service(
        permission='population.view_auditpopulation',
        exception_msg='Failed to get audit population.',
        revision_name='Get audit population',
    )
    def resolve_auditee_audit_population(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        population_id = kwargs.get('population_id')

        user = info.context.user
        audit = Audit.objects.get(id=audit_id)

        if not user_in_audit_organization(audit, user):
            raise ServiceException(f'User {user.id} cannot view audit population')

        return AuditPopulation.objects.get(audit__id=audit_id, id=population_id)

    @laika_service(
        permission='fieldwork.view_evidencecomment',
        exception_msg='Failed to get evidence comments.',
        revision_name='Get auditee evidence comments',
    )
    def resolve_auditee_evidence_comments(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        evidence_id = kwargs.get('evidence_id')
        pool = kwargs.get('pool')
        return Evidence.objects.get(id=evidence_id, audit__id=audit_id).get_comments(
            pool
        )

    @laika_service(
        permission='fieldwork.view_evidence',
        exception_msg='Failed to get auditee evidence list.',
        revision_name='Auditee all evidence',
    )
    def resolve_auditee_all_evidence(self, info, **kwargs):
        evidence = get_evidence_by_args(kwargs)

        return FieldworkEvidenceAllResponseType(evidence=evidence)

    @laika_service(
        permission='fieldwork.view_evidence',
        exception_msg='Failed to get accepted evidence count.',
        revision_name='Auditee accepted evidence count',
    )
    def resolve_auditee_accepted_evidence_count(self, info, **kwargs):
        evidence = Evidence.objects.not_deleted_evidence(kwargs=kwargs)
        return AcceptedEvidenceCountType(
            accepted_evidence=evidence.filter(status='auditor_accepted').count(),
            total_evidence=evidence.count(),
        )

    @laika_service(
        permission='fieldwork.view_evidence',
        exception_msg='Failed to get reviewed evidence count.',
        revision_name='Auditee reviewed evidence count',
    )
    def resolve_auditee_reviewed_evidence_count(self, info, **kwargs):
        evidence = Evidence.objects.not_deleted_evidence(kwargs=kwargs)
        return LaikaReviewedEvidenceCountType(
            laika_reviewed_evidence=evidence.filter(is_laika_reviewed=True).count(),
            total_evidence=evidence.count(),
        )

    @laika_service(
        permission='fieldwork.view_evidence',
        exception_msg='Failed to get evidence.',
        revision_name='Auditee evidence',
    )
    def resolve_auditee_evidence(self, info, **kwargs):
        return Evidence.objects.get(
            id=kwargs.get('evidence_id'), audit__id=kwargs.get('audit_id')
        )

    @laika_service(
        permission='fieldwork.view_evidence',
        exception_msg='Failed to get assignees for evidence',
        revision_name='Assignees for evidence',
    )
    def resolve_auditee_assignees_for_evidence(self, info, **kwargs):
        return get_assignees_for_evidence(kwargs)

    @laika_service(
        permission='fieldwork.view_evidence',
        exception_msg='Failed to get comment users',
        revision_name='Fieldwork comment users',
    )
    def resolve_auditee_evidence_comment_users(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        pool = kwargs.get('pool')
        user_role = info.context.user.role
        return get_comment_mention_users_by_pool(audit_id, pool, user_role)

    @laika_service(
        permission='fieldwork.view_evidence',
        exception_msg='Failed to get evidence documents',
        revision_name='Fieldwork evidence documents',
    )
    def resolve_auditee_documents(self, info, **kwargs):
        pagination = kwargs.get('pagination', {})
        page_size = pagination.get('page_size', DEFAULT_PAGE_SIZE)
        page = pagination.get('page')

        drive = info.context.user.organization.drive
        documents = filter_drive_evidence(drive, info, None, **kwargs)

        search_criteria = kwargs.get('search_criteria', '')
        order = kwargs.get('order_by')

        policies = info.context.user.organization.policies.filter(
            is_published=True, name__icontains=search_criteria
        )

        mapped_policies = map_policies_to_evidence_req_attachment(policies)

        audit = Audit.objects.get(id=kwargs.get('audit_id'))

        documents_related_info = get_tags_and_categories_info(
            documents, audit.audit_type
        )
        categories_filters = kwargs.get('categories_filters')
        if categories_filters:
            filter_query = Q()
            for tag in categories_filters:
                # fmt: off
                filter_query.add(
                    Q(evidence__tags__name__icontains=tag)
                    | Q(
                        evidence__system_tags__name__in=DriveEvidence
                        .objects.subtasks_with_tag(
                            info.context.user.organization, tag
                        )
                    ),
                    Q.OR,
                )
                # fmt: on
            documents = documents.filter(filter_query)

        framework_filter = kwargs.get('framework_filter')
        if framework_filter:
            documents = documents.filter_by_certs(framework_filter)

        mapped_docs = map_documents_to_evidence_req_attachment(
            documents, documents_related_info.get('tags_per_doc')
        )
        mapped_docs.extend(mapped_policies)

        if order:
            do_reverse = order.order == 'descend'
            if order.field == 'name':
                mapped_docs.sort(key=lambda doc: doc.name, reverse=do_reverse)
            if order.field == 'type':
                mapped_docs.sort(key=lambda doc: doc.evidence_type, reverse=do_reverse)
        else:
            mapped_docs.sort(key=lambda doc: doc.updated_at, reverse=True)

        mapped_docs = map_attachments_to_drive_evidence_type(mapped_docs)
        paginated_result = get_paginated_result(mapped_docs, page_size, page)

        documents_data = paginated_result.get('data')

        return FieldworkDocumentsResponseType(
            documents=documents_data,
            pagination=exclude_dict_keys(paginated_result, ['data']),
            categories=documents_related_info.get('categories'),
            have_audit_type=documents_related_info.get('have_audit_type'),
            audit_type=audit.audit_type,
        )

    @laika_service(
        permission='fieldwork.view_evidence',
        exception_msg='Failed to get auditee evidence list.',
        revision_name='Auditee evidence',
    )
    def resolve_auditee_evidence_list(self, info, **kwargs):
        evidence = get_evidence_by_args(kwargs)
        return get_evidence_by_audit(kwargs=kwargs, evidence=evidence)

    @laika_service(
        permission='audit.view_draftreportcomment',
        exception_msg='Failed to get draft report comments.',
        revision_name='Get draft report comments',
    )
    def resolve_auditee_draft_report_comments(self, info, **kwargs):
        audit = Audit.objects.get(
            organization=info.context.user.organization, id=kwargs.get('audit_id')
        )

        return DraftReportComment.objects.filter(
            audit=audit,
            comment__is_deleted=False,
        ).order_by('page', 'comment__created_at')

    @laika_service(
        permission='audit.view_draftreportcomment',
        exception_msg='Failed to get users for mentions in draft report',
        revision_name='Get mentions in draft report comments',
    )
    def resolve_auditee_draft_report_mentions_users(self, info, **kwargs):
        audit = Audit.objects.get(
            organization=info.context.user.organization, id=kwargs.get('audit_id')
        )
        return get_draft_report_mentions_users(audit)

    @laika_service(
        permission='audit.view_audit',
        exception_msg='Failed to get audit draft report.',
        revision_name='Get audit draft report',
    )
    def resolve_auditee_audit_draft_report(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        audit = Audit.objects.get(
            id=audit_id,
            organization=info.context.user.organization,
        )

        audit_status = audit.status.first()
        draft_report = audit_status.draft_report

        if not draft_report:
            raise ServiceException("Uploaded Draft Report file not found")

        return DraftReportType(name=draft_report.name, url=draft_report.url)

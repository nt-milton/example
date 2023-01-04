import graphene

from auditor.population.mutations import PopulationMutation
from auditor.population.queries import PopulationQuery
from auditor.report.mutations import ReportMutation
from auditor.report.queries import ReportQuery
from auditor.requirement.mutations import RequirementMutation
from auditor.requirement.queries import RequirementQuery
from fieldwork.inputs import EvidenceFilterInput
from fieldwork.models import Evidence
from fieldwork.types import (
    AcceptedEvidenceCountType,
    AuditCriteriaType,
    CriteriaPaginatedResponseType,
    EvidenceCommentType,
    FieldworkEvidenceResponseType,
    FieldworkEvidenceType,
    evidence_comment_pools_enum,
    evidence_status_enum,
    population_comment_pools_enum,
)
from fieldwork.utils import (
    get_assignees_for_evidence,
    get_comment_mention_users_by_pool,
    get_evidence_by_args,
    get_evidence_by_audit,
    get_pagination_info,
)
from laika.decorators import audit_service
from laika.types import OrderInputType, PaginationInputType
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.paginator import get_paginated_result
from user.constants import AUDITOR_ADMIN
from user.types import UserType

from .mutations import (
    AddAuditorEvidenceAttachment,
    AddAuditorEvidenceRequest,
    AssignAuditorEvidence,
    DeleteAuditEvidence,
    DeleteAuditorAllEvidenceAttachments,
    DeleteAuditorEvidenceAttachment,
    RenameAuditorEvidenceAttachment,
    UpdateAuditorCriteria,
    UpdateAuditorEvidence,
    UpdateAuditorEvidenceRequest,
    UpdateAuditorEvidenceStatus,
)
from .utils import get_criteria_by_args, get_criteria_by_audit_id, increment_display_id


class Mutation(PopulationMutation, RequirementMutation, ReportMutation, object):
    assign_auditor_evidence = AssignAuditorEvidence.Field()
    delete_audit_evidence = DeleteAuditEvidence.Field()
    add_auditor_evidence_attachment = AddAuditorEvidenceAttachment.Field()
    update_auditor_evidence_status = UpdateAuditorEvidenceStatus.Field()
    update_auditor_evidence = UpdateAuditorEvidence.Field()
    rename_auditor_evidence_attachment = RenameAuditorEvidenceAttachment.Field()
    delete_auditor_evidence_attachment = DeleteAuditorEvidenceAttachment.Field()
    delete_auditor_all_evidence_attachments = (
        DeleteAuditorAllEvidenceAttachments.Field()
    )

    add_auditor_evidence_request = AddAuditorEvidenceRequest.Field()
    update_auditor_evidence_request = UpdateAuditorEvidenceRequest.Field()
    update_auditor_criteria = UpdateAuditorCriteria.Field()


class Query(PopulationQuery, RequirementQuery, ReportQuery, object):
    auditor_all_evidence = graphene.Field(
        FieldworkEvidenceResponseType,
        audit_id=graphene.String(required=True),
        status=graphene.Argument(evidence_status_enum, required=False),
        order_by=graphene.Argument(OrderInputType, required=False),
        filter=graphene.List(EvidenceFilterInput, required=False),
    )
    auditor_evidence_comments = graphene.List(
        EvidenceCommentType,
        audit_id=graphene.String(required=True),
        evidence_id=graphene.String(required=True),
        pool=graphene.Argument(evidence_comment_pools_enum, required=True),
    )

    auditor_evidence = graphene.Field(
        FieldworkEvidenceType,
        evidence_id=graphene.String(required=True),
        audit_id=graphene.String(required=True),
        is_evidence_detail=graphene.Boolean(),
    )

    auditor_assignees_for_evidence = graphene.List(
        UserType, audit_id=graphene.String(required=True)
    )

    auditor_accepted_evidence_count = graphene.Field(
        AcceptedEvidenceCountType, audit_id=graphene.String(required=True)
    )

    auditor_evidence_comment_users = graphene.List(
        UserType,
        audit_id=graphene.String(required=True),
        pool=graphene.Argument(evidence_comment_pools_enum, required=True),
    )

    auditor_criteria = graphene.Field(
        CriteriaPaginatedResponseType,
        audit_id=graphene.String(required=True),
        order_by=graphene.Argument(OrderInputType, required=False),
        pagination=graphene.Argument(PaginationInputType, required=False),
        search_criteria=graphene.String(required=False),
    )

    auditor_all_criteria = graphene.List(
        AuditCriteriaType, audit_id=graphene.String(required=True)
    )

    auditor_audit_evidence = graphene.Field(
        FieldworkEvidenceResponseType,
        audit_id=graphene.String(required=True),
        status=graphene.Argument(evidence_status_enum),
        pagination=graphene.Argument(PaginationInputType, required=False),
        order_by=graphene.Argument(OrderInputType, required=False),
        filter=graphene.List(EvidenceFilterInput, required=False),
        search_criteria=graphene.String(required=False),
    )

    auditor_new_evidence_request_display_id = graphene.Field(
        FieldworkEvidenceType, audit_id=graphene.String(required=True)
    )

    auditor_comment_mention_users_with_pool = graphene.List(
        UserType,
        audit_id=graphene.String(required=True),
        pool=graphene.Argument(population_comment_pools_enum, required=True),
    )

    @audit_service(
        permission='fieldwork.view_evidence',
        exception_msg='Auditor failed to get new evidence request display id',
        revision_name='New Evidence Request',
    )
    def resolve_auditor_new_evidence_request_display_id(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        new_display_id = increment_display_id(Evidence, audit_id, 'ER')
        return Evidence(display_id=new_display_id)

    @audit_service(
        permission='fieldwork.view_evidencecomment',
        exception_msg='Failed to get evidence comments.',
        revision_name='Get auditor evidence comments',
    )
    def resolve_auditor_evidence_comments(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        evidence_id = kwargs.get('evidence_id')
        pool = kwargs.get('pool')
        return Evidence.objects.get(id=evidence_id, audit__id=audit_id).get_comments(
            pool
        )

    @audit_service(
        permission='fieldwork.view_evidence',
        exception_msg='Failed to get all evidence.',
        revision_name='Evidence list',
    )
    def resolve_auditor_all_evidence(self, info, **kwargs):
        evidence = get_evidence_by_args(kwargs)
        return FieldworkEvidenceResponseType(evidence=evidence)

    @audit_service(
        permission='fieldwork.view_evidence',
        exception_msg='Failed to get evidence.',
        revision_name='Get audit evidence',
    )
    def resolve_auditor_evidence(self, info, **kwargs):
        user = info.context.user
        if user.role == AUDITOR_ADMIN:
            return Evidence.objects.get(
                id=kwargs.get('evidence_id'), audit__id=kwargs.get('audit_id')
            )
        return Evidence.objects.get(
            id=kwargs.get('evidence_id'),
            audit__id=kwargs.get('audit_id'),
            audit__audit_team__auditor__user=user,
        )

    @audit_service(
        permission='fieldwork.view_evidence',
        exception_msg='Failed to get assignees for evidence.',
        revision_name='Get fieldwork evidence assignees',
    )
    def resolve_auditor_assignees_for_evidence(self, info, **kwargs):
        return get_assignees_for_evidence(kwargs)

    @audit_service(
        permission='fieldwork.view_evidence',
        exception_msg='Failed to get accepted evidence count.',
        revision_name='Get audit accepted evidence count',
    )
    def resolve_auditor_accepted_evidence_count(self, info, **kwargs):
        evidence = Evidence.objects.not_deleted_evidence(kwargs=kwargs)
        return AcceptedEvidenceCountType(
            accepted_evidence=evidence.filter(status='auditor_accepted').count(),
            total_evidence=evidence.count(),
        )

    @audit_service(
        permission='fieldwork.view_evidence',
        exception_msg='Failed to get users for audit comments.',
        revision_name='Get users for audit comments',
    )
    def resolve_auditor_evidence_comment_users(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        pool = kwargs.get('pool')
        user_role = info.context.user.role
        return get_comment_mention_users_by_pool(audit_id, pool, user_role)

    @audit_service(
        permission='fieldwork.view_criteria',
        exception_msg='Failed to all criteria',
        revision_name='Get all criteria',
    )
    def resolve_auditor_all_criteria(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        return get_criteria_by_audit_id(audit_id)

    @audit_service(
        permission='fieldwork.view_criteria',
        exception_msg='Failed to get audit criteria.',
        revision_name='Get audit criteria',
    )
    def resolve_auditor_criteria(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        search_criteria = kwargs.get('search_criteria')
        _, page, page_size = get_pagination_info(kwargs)

        criteria = get_criteria_by_audit_id(audit_id)

        filtered_criteria_requirement = get_criteria_by_args(search_criteria, criteria)

        paginated_result = get_paginated_result(
            filtered_criteria_requirement, page_size, page
        )

        return CriteriaPaginatedResponseType(
            criteria=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @audit_service(
        permission='fieldwork.view_evidence',
        exception_msg='Failed to get audit evidence.',
        revision_name='Get auditor evidence',
    )
    def resolve_auditor_audit_evidence(self, info, **kwargs):
        evidence = get_evidence_by_args(kwargs)
        return get_evidence_by_audit(kwargs=kwargs, evidence=evidence)

    @audit_service(
        permission='comment.view_comment',
        exception_msg='Failed to get comment mention users by pool',
        revision_name='Get comment mention users',
    )
    def resolve_auditor_comment_mention_users_with_pool(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        pool = kwargs.get('pool')
        user_role = info.context.user.role
        return get_comment_mention_users_by_pool(audit_id, pool, user_role)

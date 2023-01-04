import graphene

from auditor.utils import get_requirements_by_args, increment_display_id
from fieldwork.inputs import EvidenceFilterInput
from fieldwork.models import Requirement, RequirementComment
from fieldwork.types import (
    EvidenceRequirementType,
    FieldworkRequirementsResponseType,
    RequirementCommentType,
    RequirementType,
)
from fieldwork.utils import (
    get_audit_team_and_auditor_admins_mapped_to_usertype,
    get_pagination_info,
)
from laika.decorators import audit_service
from laika.types import OrderInputType, PaginationInputType
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.paginator import get_paginated_result
from user.constants import AUDITOR_ADMIN
from user.types import UserType


class RequirementQuery(object):
    requirement = graphene.Field(
        EvidenceRequirementType,
        requirement_id=graphene.String(required=True),
        audit_id=graphene.String(required=True),
    )

    requirements = graphene.List(
        RequirementType,
        audit_id=graphene.String(required=True),
        status=graphene.String(),
    )

    auditor_all_requirements = graphene.Field(
        FieldworkRequirementsResponseType,
        audit_id=graphene.String(required=True),
        filter=graphene.List(EvidenceFilterInput, required=False),
        order_by=graphene.Argument(OrderInputType, required=False),
        pagination=graphene.Argument(PaginationInputType, required=False),
        status=graphene.String(),
        search_criteria=graphene.String(required=False),
    )

    requirement_comments = graphene.List(
        RequirementCommentType, requirement_id=graphene.String(required=True)
    )

    requirement_audit_users = graphene.List(
        UserType,
        audit_id=graphene.String(required=True),
    )

    auditor_requirement_comment_users = graphene.List(
        UserType,
        audit_id=graphene.String(required=True),
    )

    auditor_new_requirement_display_id = graphene.Field(
        RequirementType, audit_id=graphene.String(required=True)
    )

    @audit_service(
        permission='fieldwork.view_requirement',
        exception_msg='Failed to get requirement.',
        revision_name='Get audit requirement',
    )
    def resolve_requirement(self, info, **kwargs):
        user = info.context.user
        if user.role == AUDITOR_ADMIN:
            return Requirement.objects.get(
                id=kwargs.get('requirement_id'),
                audit_id=kwargs.get('audit_id'),
                is_deleted=False,
            )
        return Requirement.objects.get(
            id=kwargs.get('requirement_id'),
            audit_id=kwargs.get('audit_id'),
            is_deleted=False,
            audit__audit_team__auditor__user=user,
        )

    @audit_service(
        permission='fieldwork.view_requirement',
        exception_msg='Failed to get requirements.',
        revision_name='Get audit requirements',
    )
    def resolve_requirements(self, info, **kwargs):
        requirements = get_requirements_by_args(kwargs)
        return requirements

    @audit_service(
        permission='fieldwork.view_requirement',
        exception_msg='Failed to get requirements for audit',
        revision_name='Get requirements for audit',
    )
    def resolve_auditor_all_requirements(self, info, **kwargs):
        requirement = get_requirements_by_args(kwargs)
        pagination, page, page_size = get_pagination_info(kwargs)

        if not pagination:
            return FieldworkRequirementsResponseType(requirement=requirement)

        paginated_result = get_paginated_result(requirement, page_size, page)

        return FieldworkRequirementsResponseType(
            requirement=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @audit_service(
        permission='fieldwork.view_requirementcomment',
        exception_msg='Failed to get requirement comments.',
        revision_name='Get requirement comments',
    )
    def resolve_requirement_comments(self, info, **kwargs):
        requirement_id = kwargs.get('requirement_id')
        requirement_comments = RequirementComment.objects.filter(
            requirement__id=requirement_id, comment__is_deleted=False
        ).order_by('comment__created_at')

        comments = [item.comment for item in requirement_comments]

        return comments

    @audit_service(
        permission='audit.view_audit',
        exception_msg='Failed to get requirement audit users.',
        revision_name='Get requirement audit users',
    )
    def resolve_requirement_audit_users(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        return get_audit_team_and_auditor_admins_mapped_to_usertype(audit_id)

    @audit_service(
        permission='fieldwork.view_requirement',
        exception_msg='Failed to get requirement comment users.',
        revision_name='Get requirement comment users',
    )
    def resolve_auditor_requirement_comment_users(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        return get_audit_team_and_auditor_admins_mapped_to_usertype(audit_id)

    @audit_service(
        permission='fieldwork.view_requirement',
        exception_msg='Auditor failed to get requirement new reference',
        revision_name='Get new Requirement',
    )
    def resolve_auditor_new_requirement_display_id(self, info, **payload):
        audit_id = payload.get('audit_id')
        incremental_requirement = increment_display_id(Requirement, audit_id, 'LCL')
        return RequirementType(display_id=incremental_requirement)

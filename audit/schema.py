import logging

import graphene
from django.db.models import Q

from audit.models import (
    Audit,
    AuditAuditor,
    AuditFirm,
    AuditFrameworkType,
    AuditorAuditFirm,
    OrganizationAuditFirm,
)
from audit.types import (
    AuditAuditorsTeamType,
    AuditFirmType,
    AuditorsResponseType,
    AuditorTeamType,
    AuditorType,
    AuditResponseType,
    AuditType,
    AuditTypesType,
    FrameworkType,
)
from audit.utils.audit import get_audit_stage_annotate
from certification.types import LogoType
from laika.auth import auditor_required
from laika.decorators import audit_service, laika_service
from laika.types import OrderInputType, PaginationInputType
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.order_by import get_order_queries
from laika.utils.paginator import get_paginated_result
from user.constants import AUDITOR_ADMIN
from user.models import Auditor
from user.types import AuditorUserResponseType

from .constants import (
    AUDIT_FRAMEWORK_TYPES,
    AUDITOR_ROLES,
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
)
from .mutations import (
    AssignAuditToAuditor,
    AuditorUpdateAuditContentStep,
    AuditorUpdateAuditStage,
    CheckAuditStatusField,
    CreateAudit,
    CreateAuditUser,
    DeleteAuditUsers,
    RemoveAuditorFromAudit,
    UpdateAuditorAuditDetails,
    UpdateAuditorRoleInAuditTeam,
    UpdateAuditorStep,
    UpdateAuditorUserPreferences,
    UpdateAuditStage,
    UpdateAuditUser,
)

logger = logging.getLogger('audit_schema')


class Mutation(object):
    auditor_update_audit_content_step = AuditorUpdateAuditContentStep.Field()
    create_audit = CreateAudit.Field()
    check_audit_status_field = CheckAuditStatusField.Field()
    update_audit_stage = UpdateAuditStage.Field()
    auditor_update_audit_stage = AuditorUpdateAuditStage.Field()
    update_auditor_step = UpdateAuditorStep.Field()
    update_auditor_audit_details = UpdateAuditorAuditDetails.Field()
    assign_audit_to_auditor = AssignAuditToAuditor.Field()
    update_auditor_role_in_audit_team = UpdateAuditorRoleInAuditTeam.Field()
    remove_auditor_from_audit = RemoveAuditorFromAudit.Field()
    create_audit_user = CreateAuditUser.Field()
    delete_audit_users = DeleteAuditUsers.Field()
    update_audit_user = UpdateAuditUser.Field()
    update_auditor_user_preferences = UpdateAuditorUserPreferences.Field()


class Query(object):
    audits_in_progress = graphene.List(AuditType)
    past_audits = graphene.List(AuditType)
    audit_types = graphene.List(AuditTypesType)
    audit = graphene.Field(AuditType, id=graphene.String(required=True))

    # Auditor queries
    auditor_audit = graphene.Field(AuditType, id=graphene.String(required=True))
    all_ongoing_audits = graphene.Field(
        AuditResponseType,
        pagination=graphene.Argument(PaginationInputType, required=False),
        order_by=graphene.Argument(OrderInputType, required=False),
        search_criteria=graphene.String(required=False),
    )
    auditor_ongoing_audits = graphene.Field(
        AuditResponseType,
        pagination=graphene.Argument(PaginationInputType, required=False),
        order_by=graphene.Argument(OrderInputType, required=False),
        search_criteria=graphene.String(required=False),
    )

    auditor_past_audits = graphene.Field(
        AuditResponseType,
        pagination=graphene.Argument(PaginationInputType, required=False),
        order_by=graphene.Argument(OrderInputType, required=False),
        search_criteria=graphene.String(required=False),
    )

    audit_team = graphene.Field(
        AuditAuditorsTeamType, id=graphene.String(required=True)
    )

    auditors = graphene.Field(
        AuditorsResponseType,
        pagination=graphene.Argument(PaginationInputType, required=False),
    )

    auditor_users = graphene.List(AuditorType)

    auditor_user = graphene.Field(AuditorUserResponseType)

    @laika_service(
        atomic=False,
        permission='audit.view_audit',
        exception_msg='Failed to get audits in progress',
    )
    def resolve_audits_in_progress(self, info):
        organization = info.context.user.organization
        audits = Audit.objects.filter(
            organization=organization, status__completed=False
        )

        return audits

    @laika_service(
        atomic=False,
        permission='audit.view_audit',
        exception_msg='Failed to get past audits',
    )
    def resolve_past_audits(self, info):
        organization = info.context.user.organization
        audit_completed_query = (
            Q(status__requested=True)
            and Q(status__initiated=True)
            and Q(status__fieldwork=True)
            and Q(status__in_draft_report=True)
            and Q(status__completed=True)
        )

        audits = (
            Audit.objects.filter(organization=organization)
            .filter(audit_completed_query)
            .order_by('-created_at')
        )
        return audits

    @audit_service(
        atomic=False,
        permission='audit.view_audit',
        exception_msg='Failed to get auditor past audits',
    )
    def resolve_auditor_past_audits(self, info, **kwargs):
        user = info.context.user
        auditor = Auditor.objects.get(user=user)

        pagination = kwargs.get('pagination')
        search_criteria = kwargs.get('search_criteria', '')
        page = pagination.page if pagination else DEFAULT_PAGE
        page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE
        audit_firm = AuditFirm.objects.get(
            name=user.auditor.audit_firms.all()[:1].get()
        )

        audit_completed_query = (
            Q(status__requested=True)
            and Q(status__initiated=True)
            and Q(status__fieldwork=True)
            and Q(status__in_draft_report=True)
            and Q(status__completed=True)
        )

        order_by_params = kwargs.get('order_by')
        if order_by_params:
            order_query = get_order_queries(
                [
                    {
                        'field': order_by_params.get('field'),
                        'order': order_by_params.get('order'),
                    }
                ]
            )
        else:
            order_query = get_order_queries(
                [{'field': 'audit_type', 'order': 'ascend'}]
            )
        audits = (
            Audit.objects.filter(audit_completed_query)
            .filter(audit_firm=audit_firm, name__icontains=search_criteria)
            .order_by(*order_query)
        )

        if not user.role == AUDITOR_ADMIN:
            audits = audits.filter(audit_team__auditor=auditor)

        paginated_result = get_paginated_result(audits, page_size, page)

        return AuditResponseType(
            audits=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @audit_service(
        atomic=False,
        permission='audit.view_audit',
        exception_msg='Failed to get audit for the given auditor.',
    )
    def resolve_auditor_audit(self, info, **kwargs):
        audit_id = kwargs.get('id')
        user = info.context.user

        if user.role == AUDITOR_ADMIN:
            audit = Audit.objects.get(id=audit_id)
        else:
            auditor = Auditor.objects.get(user=user)
            audit = Audit.objects.get(audit_team__auditor=auditor, id=audit_id)

        return audit

    @laika_service(
        atomic=False, permission='audit.view_audit', exception_msg='Failed to get audit'
    )
    def resolve_audit(self, info, **kwargs):
        audit_id = kwargs.get('id')
        organization = info.context.user.organization
        audit = Audit.objects.get(organization=organization, id=audit_id)
        return audit

    @laika_service(
        atomic=False,
        permission='audit.view_audit',
        exception_msg='Failed to get audit types.',
    )
    def resolve_audit_types(self, info):
        audit_types = []
        organization = info.context.user.organization
        audit_firms = OrganizationAuditFirm.objects.filter(
            organization=organization
        ).values_list('audit_firm__name', flat=True)
        audit_framework_type_keys = dict(AUDIT_FRAMEWORK_TYPES)
        unlocked_audit_framework_types = AuditFrameworkType.objects.filter(
            id__in=organization.unlocked_audit_frameworks.all().values_list(
                'audit_framework_type_id', flat=True
            )
        ).order_by('audit_type')

        for audit_firm in audit_firms:
            for framework in unlocked_audit_framework_types:
                audit_type = audit_framework_type_keys[framework.audit_type]
                audit_types.append(
                    AuditTypesType(
                        type=audit_type,
                        organization_name=organization.name,
                        audit_firm=AuditFirmType(
                            name=audit_firm, id=f'{audit_type}_{audit_firm}'
                        ),
                        framework=FrameworkType(
                            id=framework.id,
                            description=framework.description,
                            logo=LogoType(
                                id=framework.certification.id,
                                url=framework.certification.logo.url,
                            ),
                            type=audit_type,
                        ),
                    )
                )

        return audit_types

    @audit_service(
        atomic=False,
        permission='audit.view_audit',
        exception_msg='Failed to get all ongoing audits',
    )
    def resolve_all_ongoing_audits(self, info, **kwargs):
        pagination = kwargs.get('pagination')
        search_criteria = kwargs.get('search_criteria', '')
        page = pagination.page if pagination else DEFAULT_PAGE
        page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE

        user = info.context.user

        audit_firm = AuditFirm.objects.get(
            name=user.auditor.audit_firms.all()[:1].get()
        )
        auditor = Auditor.objects.get(user=user)
        is_admin_role = user.role == AUDITOR_ADMIN

        audit_ongoing_query = Q(status__completed=False) or Q(completed_at__isnull=True)

        order_by_params = kwargs.get('order_by')
        if order_by_params:
            order_query = get_order_queries(
                [
                    {
                        'field': order_by_params.get('field'),
                        'order': order_by_params.get('order'),
                    }
                ]
            )
        else:
            order_query = get_order_queries(
                [
                    {'field': 'stage', 'order': 'ascend'},
                    {'field': 'audit_type', 'order': 'ascend'},
                ]
            )

        ongoing_audits = (
            Audit.objects.filter(audit_ongoing_query)
            .filter(audit_firm=audit_firm, name__icontains=search_criteria)
            .annotate(stage=get_audit_stage_annotate())
            .order_by(*order_query)
        )

        if not is_admin_role:
            ongoing_audits = ongoing_audits.filter(audit_team__auditor=auditor)

        paginated_result = get_paginated_result(ongoing_audits, page_size, page)

        return AuditResponseType(
            audits=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @audit_service(
        atomic=False,
        permission='audit.view_audit',
        exception_msg='Failed to get auditor ongoing audits',
    )
    def resolve_auditor_ongoing_audits(self, info, **kwargs):
        user = info.context.user
        auditor = Auditor.objects.get(user=user)
        pagination = kwargs.get('pagination')
        search_criteria = kwargs.get('search_criteria', '')
        page = pagination.page if pagination else DEFAULT_PAGE
        page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE
        audit_firm = AuditFirm.objects.get(
            name=user.auditor.audit_firms.all()[:1].get()
        )

        order_by_params = kwargs.get('order_by')
        if order_by_params:
            order_query = get_order_queries(
                [
                    {
                        'field': order_by_params.get('field'),
                        'order': order_by_params.get('order'),
                    }
                ]
            )
        else:
            order_query = get_order_queries(
                [
                    {'field': 'stage', 'order': 'ascend'},
                    {'field': 'audit_type', 'order': 'ascend'},
                ]
            )

        audit_ongoing_query = Q(status__completed=False) or Q(completed_at__isnull=True)

        audits = (
            Audit.objects.filter(audit_ongoing_query)
            .filter(
                audit_team__auditor=auditor,
                audit_firm=audit_firm,
                name__icontains=search_criteria,
            )
            .annotate(stage=get_audit_stage_annotate())
            .order_by(*order_query)
        )

        paginated_result = get_paginated_result(audits, page_size, page)

        return AuditResponseType(
            audits=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @audit_service(
        atomic=False,
        permission='audit.view_audit',
        exception_msg='Failed to get auditors associated to audit',
    )
    def resolve_audit_team(self, info, **kwargs):
        audit_id = kwargs.get('id')
        auditors_for_audit = AuditAuditor.objects.filter(audit_id=audit_id)
        auditors = []
        for a in auditors_for_audit:
            auditors.append(AuditorTeamType(user=a.auditor.user, role=a.title_role))
        return AuditAuditorsTeamType(id=id, auditors=auditors)

    @audit_service(
        atomic=False,
        permission='audit.view_audit',
        exception_msg='Failed to get auditors',
    )
    def resolve_auditors(self, info, **kwargs):
        pagination = kwargs.get('pagination')
        page = pagination.page if pagination else DEFAULT_PAGE
        page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE

        user = info.context.user
        audit_firms = user.auditor.audit_firms.all()

        auditors = Auditor.objects.filter(audit_firms__in=audit_firms).exclude(
            user__email=user.email
        )

        paginated_result = get_paginated_result(auditors, page_size, page)

        return AuditorsResponseType(
            auditors=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @audit_service(
        atomic=False,
        permission='audit.view_audit_firm_auditors',
        exception_msg='Failed to get all auditor users',
    )
    def resolve_auditor_users(self, info):
        user = info.context.user
        user_audit_firm = Auditor.objects.get(user=user).audit_firms.first()
        return Auditor.objects.filter(
            user__role__in=AUDITOR_ROLES.values(), audit_firms__in=[user_audit_firm]
        )

    @auditor_required
    def resolve_auditor_user(self, info, **kwargs):
        user = info.context.user
        audit_firm = ''
        auditor_audit_firm = AuditorAuditFirm.objects.filter(auditor__user=user).first()
        if auditor_audit_firm:
            audit_firm = auditor_audit_firm.audit_firm.name
        return AuditorUserResponseType(data=user, audit_firm=audit_firm)

import graphene
from django.contrib.postgres.fields import ArrayField
from django.db.models import CharField, Count, F, Func, IntegerField, TextField, Value
from django.db.models.functions import Cast, Coalesce, NullIf, Upper
from django.db.models.query import Prefetch
from django.db.models.query_utils import Q

from action_item.models import ActionItem
from control.constants import REQUIRED_EVIDENCE_NO
from control.helpers import get_filter_health, get_filter_query, get_health_stats
from control.models import Control, ControlPillar
from control.mutations import (
    AddControlActionItem,
    AddControlEvidence,
    BulkUpdateControlActionItems,
    CreateControl,
    DeleteControl,
    DeleteControlEvidence,
    DeleteControls,
    MigrateOrganizationToMyCompliance,
    UpdateControl,
    UpdateControlActionItem,
    UpdateControlFamilyOwner,
    UpdateControls,
)
from control.types import (
    ControlActionItemType,
    ControlBannerCounterResponseType,
    ControlEvidenceResponseType,
    ControlPillarType,
    ControlsFiltersResponseType,
    ControlsPerPillar,
    ControlsResponseType,
    ControlType,
)
from control.utils.filter_builder import FilterBuilder
from evidence.models import Evidence
from laika.auth import login_required, permission_required
from laika.decorators import laika_service
from laika.types import PaginationInputType
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.exceptions import service_exception
from laika.utils.order_by import get_order_queries
from laika.utils.paginator import get_paginated_result
from laika.utils.permissions import map_permissions
from organization.filters import roadmap_filter_query
from organization.inputs import RoadmapFilterInputType

from .constants import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    HIGHEST_CHAR_INDEX,
    HIGHEST_NUM_INDEX,
)


class Mutation(graphene.ObjectType):
    create_control = CreateControl.Field()
    update_control = UpdateControl.Field()
    delete_control = DeleteControl.Field()
    delete_controls = DeleteControls.Field()
    add_control_evidence = AddControlEvidence.Field()
    delete_control_evidence = DeleteControlEvidence.Field()
    update_controls = UpdateControls.Field()
    add_control_action_item = AddControlActionItem.Field()
    update_control_action_item = UpdateControlActionItem.Field()
    migrate_organization_to_my_compliance = MigrateOrganizationToMyCompliance.Field()
    update_control_family_owner = UpdateControlFamilyOwner.Field()
    bulk_update_control_action_items = BulkUpdateControlActionItems.Field()


def set_order(control_health):
    action_order = {
        'FLAGGED': 0,
        'NO_DATA': 1,
        'NOT_IMPLEMENTED': 2,
        'NO_MONITORS': 3,
        'HEALTHY': 4,
    }

    def order_by_health(control):
        if control.id not in control_health:
            return action_order.get('NOT_IMPLEMENTED')

        health = control_health[control.id]
        return action_order.get(health, 4)

    return order_by_health


class FiltersControlType(graphene.InputObjectType):
    status = graphene.List(graphene.String)
    health = graphene.List(graphene.String)
    framework = graphene.List(graphene.String)
    pillar = graphene.List(graphene.String)
    tag = graphene.List(graphene.String)
    owners = graphene.List(graphene.String)
    search = graphene.String()


class Query(object):
    control = graphene.Field(ControlType, id=graphene.UUID(required=True))
    controls = graphene.Field(
        ControlsResponseType,
        names=graphene.List(graphene.String),
        page_size=graphene.Int(),
        page=graphene.Int(),
        filters=graphene.Argument(FiltersControlType),
    )

    control_evidence = graphene.Field(
        ControlEvidenceResponseType,
        id=graphene.UUID(required=True),
        pagination=graphene.Argument(PaginationInputType, required=False),
    )

    pillars = graphene.List(ControlPillarType)

    controls_filters = graphene.Field(ControlsFiltersResponseType)

    control_action_items = graphene.List(
        ControlActionItemType, id=graphene.UUID(required=True)
    )

    controls_per_family = graphene.List(ControlsPerPillar)

    control_banner_counter = graphene.Field(
        ControlBannerCounterResponseType,
        filters=graphene.Argument(RoadmapFilterInputType),
    )

    @login_required
    @service_exception('Cannot get control details')
    @permission_required('control.view_control')
    def resolve_control(self, info, **kwargs):
        id = kwargs.get('id')
        organization_id = info.context.user.organization_id

        return Control.objects.get(id=id, organization_id=organization_id)

    @login_required
    @service_exception('Cannot get control evidence')
    @permission_required('control.view_control')
    def resolve_control_evidence(self, info, **kwargs):
        id = kwargs.get('id')
        pagination = kwargs.get('pagination')
        organization_id = info.context.user.organization_id
        control = Control.objects.get(id=id, organization_id=organization_id)
        data = Evidence.objects.filter(
            Q(controls=control) | Q(action_items__controls=control)
        ).distinct()
        page = pagination.page if pagination else DEFAULT_PAGE
        page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE
        paginated_result = get_paginated_result(data, page_size, page)
        paginated_result['id'] = 'control-evidence'
        return ControlEvidenceResponseType(
            data=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @login_required
    @service_exception('Cannot get controls')
    def resolve_controls(self, info, **kwargs):
        organization_id = info.context.user.organization_id

        page_size = kwargs.get('page_size') or 200
        names = kwargs.get('names')
        filters = kwargs.get('filters', {})

        organization_controls = Control.objects.filter(
            organization_id=organization_id
        ).select_related(
            'owner1', 'owner2', 'owner3', 'administrator', 'approver', 'organization'
        )

        controls_health = Control.controls_health(organization_id)

        health_stats = get_health_stats(controls_health)
        filter_query = get_filter_query(filters, names, info.context.user.organization)

        # ref_char gets the character part of the reference_id
        # ref_num gets the numeric part of the reference_id
        # the Coalesce is used when the control has no reference_id
        data = sorted(
            organization_controls.annotate(
                status_uppercase=Upper('status'),
                ref_char=Func(
                    Coalesce('reference_id', Value(HIGHEST_CHAR_INDEX)),
                    Value(r'\D+'),
                    function='regexp_matches',
                    output_field=ArrayField(TextField()),
                ),
                ref_num=Cast(
                    Func(
                        Coalesce('reference_id', Value(HIGHEST_NUM_INDEX)),
                        Value(r'\d+'),
                        function='regexp_matches',
                    ),
                    output_field=ArrayField(IntegerField()),
                ),
            )
            .filter(filter_query)
            .distinct()
            .order_by('ref_char', 'ref_num', 'display_id'),
            key=set_order(controls_health),
        )

        data = get_filter_health(filters, data, controls_health)

        page = kwargs.get('page')
        paginated_result = get_paginated_result(data, page_size, page)
        data = paginated_result.get('data')

        permissions = map_permissions(info.context.user, 'control')

        return ControlsResponseType(
            data=data,
            pagination=exclude_dict_keys(paginated_result, ['data']),
            permissions=permissions,
            health_stats=health_stats,
        )

    @laika_service(
        permission='control.view_control', exception_msg='Cannot get control details'
    )
    def resolve_pillars(self, info, **kwargs):
        return ControlPillar.objects.all()

    @laika_service(
        permission='control.view_control',
        exception_msg='Cannot get control filters',
        revision_name='Controls Filters',
    )
    def resolve_controls_filters(self, info, **kwargs):
        organization_id = info.context.user.organization_id
        builder = FilterBuilder()
        builder.add_status(organization_id)
        builder.add_health(organization_id)
        builder.add_frameworks(organization_id)
        builder.add_pillars(organization_id)
        builder.add_tags(organization_id)
        builder.add_owners(organization_id)

        filters_list = builder.export()
        return ControlsFiltersResponseType(data=filters_list)

    @laika_service(
        permission='action_item.view_actionitem',
        exception_msg='Cannot get control\'s action items',
    )
    def resolve_control_action_items(self, info, **kwargs):
        # TODO - remove annotate when data issues for requiredEvidence
        # metadata field are solved
        control_action_items = (
            ActionItem.objects.filter(controls__id=kwargs.get('id'))
            .prefetch_related('controls')
            .prefetch_related('evidences')
            .annotate(
                require_evidence=Coalesce(
                    NullIf(
                        Cast(F('metadata__requiredEvidence'), output_field=CharField()),
                        Value(''),
                    ),
                    Value(REQUIRED_EVIDENCE_NO),
                )
            )
        )

        order_query = get_order_queries(
            [
                {'field': 'display_id', 'order': 'ascend'},
                {'field': 'is_required', 'order': 'descend'},  # True values first
                {'field': 'metadata__isCustom', 'order': 'descend'},
                {'field': 'is_recurrent', 'order': 'descend'},
                {'field': 'due_date', 'order': 'ascend'},
                {'field': 'metadata__referenceId', 'order': 'ascend'},
            ]
        )

        return control_action_items.order_by(*order_query)

    @login_required
    @laika_service(
        permission='control.view_control',
        exception_msg='Failed to get controls per family',
        revision_name='Controls Per Family',
    )
    def resolve_controls_per_family(self, info, **kwargs):
        organization = info.context.user.organization
        controls_per_pillar = []
        pillars = ControlPillar.objects.prefetch_related(
            Prefetch(
                'control',
                queryset=Control.objects.filter(organization=organization).order_by(
                    'reference_id', 'display_id'
                ),
                to_attr='controls_list',
            )
        ).order_by('name')

        for pillar in pillars:
            if len(pillar.controls_list):
                controls_per_pillar.append(
                    {
                        'family_name': pillar.full_name,
                        'id': pillar.id,
                        'family_controls': pillar.controls_list,
                    }
                )

        return controls_per_pillar

    @laika_service(
        permission='control.view_control',
        exception_msg='Cannot get control banner counter',
        revision_name='Controls Banner Counter',
    )
    def resolve_control_banner_counter(self, info, **kwargs):
        organization_id = info.context.user.organization_id
        filter_query = roadmap_filter_query(kwargs.get('filters'))
        filter_query.add(Q(organization=organization_id), Q.AND)
        controls = Control.objects.filter(filter_query).aggregate(
            assigned=Count('pk', filter=Q(owner1__isnull=False)), total=Count('pk')
        )

        return ControlBannerCounterResponseType(
            total_controls=controls['total'], assigned_controls=controls['assigned']
        )

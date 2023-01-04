import graphene

from blueprint.filters import get_status_filters
from blueprint.helpers import (
    annotate_blueprint_controls_prescribed,
    blueprint_controls_search_criteria,
    get_filter_blueprint_controls,
)
from blueprint.models.control_family import ControlFamilyBlueprint
from blueprint.models.history import BlueprintHistory
from blueprint.mutations import PrescribeContent, PrescribeControls, UnprescribeControls
from blueprint.types import (
    AllBlueprintControlsResponseType,
    AllBlueprintHistoryResponseType,
    BlueprintControlsResponseType,
    BlueprintHistoryType,
    ControlBlueprintFilterType,
    ControlFamilyBlueprintType,
)
from laika.decorators import concierge_service
from laika.types import FiltersType, OrderInputType, PaginationInputType
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.paginator import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, get_paginated_result


class Query(object):
    blueprint_controls = graphene.Field(
        BlueprintControlsResponseType,
        organization_id=graphene.String(required=True),
        pagination=graphene.Argument(PaginationInputType, required=False),
        order_by=graphene.Argument(OrderInputType, required=False),
        filter=graphene.Argument(
            graphene.List(ControlBlueprintFilterType), required=False
        ),
        search_criteria=graphene.String(required=False),
    )

    all_blueprint_controls = graphene.Field(
        AllBlueprintControlsResponseType,
        organization_id=graphene.String(required=True),
        filter=graphene.Argument(
            graphene.List(ControlBlueprintFilterType), required=False
        ),
        search_criteria=graphene.String(required=False),
    )

    blueprint_control_families = graphene.List(ControlFamilyBlueprintType)
    blueprint_control_status = graphene.Field(FiltersType)
    all_blueprint_history = graphene.Field(
        AllBlueprintHistoryResponseType, organization_id=graphene.String(required=True)
    )
    blueprint_history = graphene.Field(
        BlueprintHistoryType, organization_id=graphene.String(required=True)
    )

    @concierge_service(
        permission='blueprint.view_controlblueprint',
        exception_msg='Failed to view blueprint controls',
        revision_name='Can view blueprint controls',
    )
    def resolve_blueprint_controls(self, info, **kwargs):
        pagination = kwargs.get('pagination')
        order_by = kwargs.get('order_by')
        filter_by = kwargs.get('filter', {})
        search_criteria = kwargs.get('search_criteria')
        organization_id = kwargs.get('organization_id')
        page = pagination.page if pagination else DEFAULT_PAGE
        page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE

        blueprint_controls = annotate_blueprint_controls_prescribed(organization_id)

        blueprint_controls = blueprint_controls.filter(
            get_filter_blueprint_controls(filter_by)
        ).distinct()

        if search_criteria:
            blueprint_controls = blueprint_controls.filter(
                blueprint_controls_search_criteria(search_criteria)
            )

        if order_by:
            field = order_by.get('field')
            query_string = '-' + field if order_by.get('order') == 'descend' else field
            blueprint_controls = blueprint_controls.order_by(query_string)

        paginated_result = get_paginated_result(blueprint_controls, page_size, page)

        return BlueprintControlsResponseType(
            data=paginated_result['data'],
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @concierge_service(
        permission='blueprint.view_controlblueprint',
        exception_msg='Failed to view all blueprint controls',
        revision_name='Can view all blueprint controls',
    )
    def resolve_all_blueprint_controls(self, info, **kwargs):
        filter_by = kwargs.get('filter', {})
        search_criteria = kwargs.get('search_criteria')
        organization_id = kwargs.get('organization_id')

        blueprint_controls = annotate_blueprint_controls_prescribed(organization_id)

        blueprint_controls = blueprint_controls.filter(
            get_filter_blueprint_controls(filter_by)
        ).distinct()

        if search_criteria:
            blueprint_controls = blueprint_controls.filter(
                blueprint_controls_search_criteria(search_criteria)
            )

        return BlueprintControlsResponseType(data=blueprint_controls)

    @concierge_service(
        permission='blueprint.view_controlblueprint',
        exception_msg='Failed to view blueprint control families',
        revision_name='Can view blueprint control families',
    )
    def resolve_blueprint_control_families(self, info, **kwargs):
        return ControlFamilyBlueprint.objects.all().order_by('name')

    @concierge_service(
        permission='blueprint.view_controlblueprint',
        exception_msg='Failed to view blueprint control families',
        revision_name='Can view blueprint control families',
    )
    def resolve_blueprint_control_status(self, info, **kwargs):
        return get_status_filters()

    @concierge_service(
        atomic=False,
        permission='user.view_concierge',
        exception_msg='Failed to view Blueprint History ',
    )
    def resolve_all_blueprint_history(self, info, **kwargs):
        blueprint_history_entries = BlueprintHistory.objects.filter(
            organization_id=kwargs.get('organization_id')
        ).order_by('-created_at')
        return AllBlueprintHistoryResponseType(
            blueprint_data_entries=blueprint_history_entries
        )

    @concierge_service(
        atomic=False,
        permission='user.view_concierge',
        exception_msg='Failed to get Blueprint History ',
    )
    def resolve_blueprint_history(self, info, **kwargs):
        return (
            BlueprintHistory.objects.filter(
                organization_id=kwargs.get('organization_id')
            )
            .order_by('-created_at')
            .first()
        )


class Mutation(graphene.ObjectType):
    prescribe_controls = PrescribeControls.Field()
    unprescribe_controls = UnprescribeControls.Field()
    prescribe_content = PrescribeContent.Field()

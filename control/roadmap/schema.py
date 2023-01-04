import graphene
from django.db.models import Q, QuerySet

from control.models import Control, ControlGroup
from control.roadmap.mutations import (
    CreateControlGroup,
    DeleteControlGroup,
    MoveControlsToControlGroup,
    UpdateControlGroup,
    UpdateControlGroupSortOrder,
    UpdateControlGroupWeb,
    UpdateControlSortOrder,
)
from control.roadmap.types import ControlGroupType
from control.types import ControlType
from laika.decorators import concierge_service


def filter_backlog_controls(backlog: QuerySet[Control], token: str):
    return (
        backlog.filter(Q(name__icontains=token) | Q(reference_id__icontains=token))
        .order_by('display_id')
        .distinct()
    )


def sort_by_order(group: ControlGroupType):
    return group.sort_order  # type: ignore


def map_controls_to_group(
    controls: QuerySet[Control], organization_id: str
) -> list[ControlGroupType]:
    groups_dictionary = {}  # type: ignore

    empty_groups = ControlGroup.objects.filter(
        roadmap__organization_id=organization_id, controls__isnull=True
    ).distinct()

    for empty_group in empty_groups:
        groups_dictionary[empty_group.id] = empty_group

    for control in controls:
        selected_group = control.group.all().first()
        if groups_dictionary.get(selected_group.id):
            groups_dictionary[selected_group.id].controls.append(control)
        else:
            new_group = ControlGroupType(
                id=selected_group.id,
                reference_id=selected_group.reference_id,
                name=selected_group.name,
                start_date=selected_group.start_date,
                due_date=selected_group.due_date,
                sort_order=selected_group.sort_order,
                controls=[control],
            )
            groups_dictionary[selected_group.id] = new_group

    groups = [groups_dictionary[key] for key in groups_dictionary]
    groups.sort(key=sort_by_order)
    return groups


class Query(object):
    groups = graphene.List(
        ControlGroupType,
        organization_id=graphene.String(required=True),
        search_criteria=graphene.String(),
        filtered_unlocked_framework=graphene.String(),
    )

    all_groups = graphene.List(
        ControlGroupType, organization_id=graphene.String(required=True)
    )

    backlog = graphene.List(
        ControlType,
        organization_id=graphene.String(required=True),
        search_criteria=graphene.String(),
        filtered_unlocked_framework=graphene.String(),
    )

    @concierge_service(
        permission='control.view_roadmap',
        exception_msg='Failed to view roadmap configuration',
    )
    def resolve_groups(self, info, **kwargs):
        organization_id = kwargs.get('organization_id')
        search_criteria = kwargs.get('search_criteria')
        filtered_unlocked_framework = kwargs.get('filtered_unlocked_framework')

        query_set = (
            Control.objects.filter(organization_id=organization_id)
            .filter(~Q(group=None))
            .order_by('display_id')
            .distinct()
        )

        if filtered_unlocked_framework:
            query_set = query_set.filter(
                Q(reference_id__endswith=filtered_unlocked_framework)
            )

        if search_criteria:
            search_query = Q()
            for token in search_criteria.strip().split(' '):
                token_query = Q(
                    Q(name__icontains=token) | Q(reference_id__icontains=token)
                )
                search_query.add(token_query, Q.OR)

            return map_controls_to_group(
                query_set.filter(search_query), organization_id
            )

        return map_controls_to_group(query_set, organization_id)

    @concierge_service(
        permission='control.view_roadmap',
        exception_msg='Failed to view roadmap configuration',
    )
    def resolve_all_groups(self, info, **kwargs):
        return ControlGroup.objects.filter(
            roadmap__organization_id=kwargs.get('organization_id')
        ).order_by('sort_order')

    @concierge_service(
        permission='control.view_roadmap',
        exception_msg='Failed to view roadmap configuration',
    )
    def resolve_backlog(self, info, **kwargs):
        organization_id = kwargs.get('organization_id')
        search_criteria = kwargs.get('search_criteria')
        filtered_unlocked_framework = kwargs.get('filtered_unlocked_framework')

        backlog = Control.objects.filter(organization__id=organization_id, group=None)

        if filtered_unlocked_framework:
            backlog = backlog.filter(reference_id__endswith=filtered_unlocked_framework)

        if search_criteria:
            search_query = Q()
            for token in search_criteria.strip().split(' '):
                token_query = Q(
                    Q(name__icontains=token) | Q(reference_id__icontains=token)
                )
                search_query.add(token_query, Q.OR)

            return backlog.filter(search_query)

        return backlog.order_by('display_id')


class Mutation(graphene.ObjectType):
    update_control_group = UpdateControlGroup.Field()
    update_control_group_web = UpdateControlGroupWeb.Field()
    delete_control_group = DeleteControlGroup.Field()
    update_control_group_sort_order = UpdateControlGroupSortOrder.Field()
    update_control_sort_order = UpdateControlSortOrder.Field()
    move_controls_to_control_group = MoveControlsToControlGroup.Field()
    create_control_group = CreateControlGroup.Field()

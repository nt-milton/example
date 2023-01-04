import logging

import graphene
from django.db import models
from django.db.models import OuterRef, Subquery

from action_item.models import ActionItem, ActionItemStatus
from control.helpers import annotate_action_items_control_count
from control.models import Control, ControlGroup, RoadMap
from control.roadmap.inputs import (
    CreateControlGroupInput,
    DeleteGroupInput,
    MoveControlsToControlGroupInput,
    UpdateControlGroupInput,
    UpdateControlGroupSortOrderInput,
    UpdateControlSortOrderInput,
)
from control.roadmap.types import ControlGroupType
from laika.decorators import concierge_service, laika_service
from laika.utils.dates import validate_timeline_dates
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.exceptions import ServiceException

from .helpers import get_reference_id, get_untitled_name, shift_new_group_to_top

logger = logging.getLogger(__name__)
ERROR = 'An error happened, please try again'
BACKLOG_GROUP_ID = 0


class CreateControlGroup(graphene.Mutation):
    class Arguments:
        input = CreateControlGroupInput(required=True)

    control_group = graphene.Field(ControlGroupType)

    @concierge_service(
        permission='control.add_controlgroup',
        exception_msg='Failed to add control group',
        revision_name='Can add control group',
    )
    def mutate(self, info, input: CreateControlGroupInput):
        try:
            roadmap = RoadMap.objects.get(
                organization__id=input.organization_id,
            )
            name = get_untitled_name(roadmap)
            reference_id = get_reference_id(roadmap)

            control_group = ControlGroup.objects.create(
                name=name, roadmap=roadmap, reference_id=reference_id
            )

            shift_new_group_to_top(control_group, roadmap)

            return CreateControlGroup(control_group=control_group)
        except Exception:
            return ServiceException(ERROR)


def get_closest_date_subquery(date_type):
    return Subquery(
        ControlGroup.objects.filter(controls__action_items__id=OuterRef('id'))
        .distinct()
        .values(date_type)
        .order_by(date_type)[:1]
    )


def update_shared_action_items_dates(shared_action_items):
    annotated_action_items = shared_action_items.annotate(
        control_group_closest_start_date=get_closest_date_subquery('start_date'),
        control_group_closest_due_date=get_closest_date_subquery('due_date'),
    )

    for action_item in annotated_action_items:
        action_item.start_date = action_item.control_group_closest_start_date
        action_item.due_date = action_item.control_group_closest_due_date

    ActionItem.objects.bulk_update(annotated_action_items, ['start_date', 'due_date'])


def update_action_items_when_update_control_group(control_group, start_date, due_date):
    if not start_date and not due_date:
        return
    action_items_with_control_count = annotate_action_items_control_count()

    new_required_action_items = action_items_with_control_count.filter(
        controls__group__in=control_group,
        is_required=True,
        status=ActionItemStatus.NEW,
    ).distinct()

    shared_action_items = new_required_action_items.filter(control_count__gt=1)
    update_shared_action_items_dates(shared_action_items)

    new_required_action_items.filter(control_count=1).update(
        start_date=start_date, due_date=due_date
    )


def update_control_group_fields_m(input):
    group_id = input.get('id')
    start_date = input.get('start_date')
    due_date = input.get('due_date')
    control_group = ControlGroup.objects.filter(pk=group_id)

    validate_timeline_dates(start_date, due_date)
    control_group.update(**exclude_dict_keys(input, ['id']))

    update_action_items_when_update_control_group(control_group, start_date, due_date)


class UpdateControlGroup(graphene.Mutation):
    class Arguments:
        input = UpdateControlGroupInput(required=True)

    control_group = graphene.Field(ControlGroupType)

    @concierge_service(
        permission='control.change_roadmap',
        exception_msg='Failed to update group',
        revision_name='Can change roadmap',
    )
    def mutate(self, info, input):
        update_control_group_fields_m(input)
        return UpdateControlGroup(
            control_group=ControlGroup.objects.get(id=input.get('id'))
        )


class UpdateControlGroupWeb(graphene.Mutation):
    class Arguments:
        input = UpdateControlGroupInput(required=True)

    control_group = graphene.Field(ControlGroupType)

    @laika_service(
        permission='control.change_roadmap',
        exception_msg='Failed to update group',
        revision_name='Can change roadmap',
    )
    def mutate(self, info, input):
        update_control_group_fields_m(input)

        return UpdateControlGroupWeb(
            control_group=ControlGroup.objects.get(id=input.get('id'))
        )


class DeleteControlGroup(graphene.Mutation):
    class Arguments:
        input = DeleteGroupInput(required=True)

    success = graphene.Boolean(default_value=True)

    @concierge_service(
        permission='control.delete_controlgroup',
        exception_msg='Failed to delete group',
        revision_name='Group deleted',
    )
    def mutate(self, info, input):
        group_id = input.get('id')
        organization_id = input.get('organization_id')

        control_group = ControlGroup.objects.filter(pk=group_id)
        control_group.delete()

        base_groups = ControlGroup.objects.filter(
            roadmap__organization_id=organization_id
        ).order_by('sort_order')

        if len(base_groups) > 0:
            for index, group in enumerate(base_groups):
                new_order = index + 1
                ControlGroup.objects.filter(pk=group.id).update(sort_order=new_order)

        return DeleteControlGroup()


class UpdateControlGroupSortOrder(graphene.Mutation):
    class Arguments:
        input = UpdateControlGroupSortOrderInput(required=True)

    success = graphene.Boolean()

    @concierge_service(
        permission='control.change_roadmap',
        exception_msg='Failed to update control group sort order',
        revision_name='Can change roadmap',
    )
    def mutate(self, info, input: UpdateControlGroupSortOrderInput):
        try:
            for control_group in input.control_groups:
                ControlGroup.objects.filter(
                    id=control_group.id, roadmap__organization_id=input.organization_id
                ).update(**exclude_dict_keys(dict(control_group), ['id']))

            return UpdateControlGroupSortOrder(success=True)
        except Exception:
            return ServiceException(ERROR)


class UpdateControlSortOrder(graphene.Mutation):
    class Arguments:
        input = UpdateControlSortOrderInput(required=True)

    success = graphene.Boolean()

    @concierge_service(
        permission='control.change_roadmap',
        exception_msg='Failed to update control sort order',
        revision_name='Can change roadmap',
    )
    def mutate(self, info, input: UpdateControlSortOrderInput):
        try:
            for index, control_id in enumerate(input.controls):
                Control.objects.filter(id=control_id).update(display_id=index + 1)

            return UpdateControlSortOrder(success=True)
        except Exception:
            return ServiceException(ERROR)


class MoveControlsToControlGroup(graphene.Mutation):
    class Arguments:
        input = MoveControlsToControlGroupInput(required=True)

    success = graphene.Boolean()

    @concierge_service(
        permission='control.change_control',
        exception_msg='Failed to move controls between groups',
        revision_name='Controls moved',
    )
    def mutate(self, info, input: MoveControlsToControlGroupInput):
        receiver_group = None
        try:
            if input.group_id == BACKLOG_GROUP_ID:
                controls_in_group = Control.objects.filter(
                    organization__id=input.organization_id, group=None
                )
            else:
                receiver_group = ControlGroup.objects.get(id=input.group_id)
                controls_in_group = receiver_group.controls.all()

            last_control_display_id = (
                controls_in_group.aggregate(largest=models.Max('display_id'))['largest']
                if controls_in_group.exists()
                else 0
            )

            for index, control in enumerate(
                Control.objects.filter(id__in=input.control_ids)
            ):
                control.group.clear()
                if input.group_id != BACKLOG_GROUP_ID:
                    control.group.add(receiver_group)
                control.display_id = last_control_display_id + (index + 1)

                control.save()

            if receiver_group and (
                receiver_group.start_date or receiver_group.due_date
            ):
                update_action_items_when_update_control_group(
                    [receiver_group], receiver_group.start_date, receiver_group.due_date
                )

            return MoveControlsToControlGroup(success=True)
        except Exception as e:
            logger.warning(f'{ERROR}: {e}')
            return ServiceException(ERROR)

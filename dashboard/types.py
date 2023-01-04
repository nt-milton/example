import graphene
from graphene_django.types import DjangoObjectType

import action_item
from action_item.constants import TYPE_ACCESS_REVIEW, TYPE_POLICY, TYPE_QUICK_START
from dashboard.models import (
    NON_SUBTYPE_TASK_TYPES,
    ActionItem,
    ActionItemMetadata,
    TaskView,
    UserTask,
)
from dashboard.utils import (
    get_dashboard_action_item_metadata,
    get_dashboard_action_item_subtype,
    get_dashboard_action_item_type,
)
from laika.types import PaginationResponseType
from program.constants import SUBTASK_COMPLETED_STATUS, SUBTASK_GROUP


class ActionItemTypeV2(DjangoObjectType):
    class Meta:
        model = action_item.models.ActionItem


class TaskViewType(DjangoObjectType):
    class Meta:
        model = TaskView
        fields = (
            'id',
            'model_id',
            'reference_id',
            'reference_name',
            'is_required',
            'is_recurrent',
            'unique_action_item_id',
            'start_date',
            'due_date',
            'completed_on',
            'status',
            'group',
            'description',
            'reference_url',
            'assignee',
        )

    seen = graphene.Boolean()
    type = graphene.String()
    subtype = graphene.String()
    subtask_text = graphene.String()
    metadata = graphene.JSONString()

    def resolve_seen(self, info):
        if self.status == SUBTASK_COMPLETED_STATUS:
            return True
        return self.seen_action_item

    def resolve_type(self, info):
        return get_dashboard_action_item_type(self.type)

    def resolve_subtype(self, info):
        return get_dashboard_action_item_subtype(
            self.type, self.model_id, self.unique_action_item_id
        )

    def resolve_subtask_text(self, info):
        return ''

    def resolve_metadata(self, info):
        return get_dashboard_action_item_metadata(
            self.type, self.model_id, self.unique_action_item_id
        )


class ActionItemType(DjangoObjectType):
    class Meta:
        model = ActionItem
        fields = (
            'id',
            'model_id',
            'reference_id',
            'reference_name',
            'is_required',
            'is_recurrent',
            'unique_action_item_id',
            'start_date',
            'due_date',
            'completed_on',
            'status',
            'group',
            'description',
            'reference_url',
            'assignee',
        )

    seen = graphene.Boolean()
    type = graphene.String()
    subtype = graphene.String()
    group = graphene.String()
    subtask_text = graphene.String()
    metadata = graphene.JSONString()

    def resolve_seen(self, info):
        if self.status == SUBTASK_COMPLETED_STATUS:
            return True
        return self.seen_action_item

    def resolve_type(self, info):
        return get_dashboard_action_item_type(self.type)

    def resolve_group(self, info):
        non_allowed_types = NON_SUBTYPE_TASK_TYPES + [
            TYPE_QUICK_START,
            TYPE_POLICY,
            TYPE_ACCESS_REVIEW,
        ]
        if self.type in non_allowed_types:
            return 'group'
        d = dict(SUBTASK_GROUP)
        return d[self.group]

    def resolve_subtask_text(self, info):
        return self.subtask_text

    def resolve_subtype(self, info):
        return get_dashboard_action_item_subtype(
            self.type, self.model_id, self.unique_action_item_id
        )

    def resolve_metadata(self, info):
        return get_dashboard_action_item_metadata(
            self.type, self.model_id, self.unique_action_item_id
        )


class ActionItemMetadataType(DjangoObjectType):
    class Meta:
        model = ActionItemMetadata
        fields = ('action_item_id', 'seen', 'assignee')


class UserTaskType(DjangoObjectType):
    class Meta:
        model = UserTask
        fields = ('id', 'due_date', 'completed_on', 'seen', 'status', 'assignee')
        convert_choices_to_enum = False


class ActionItemResponseType(graphene.ObjectType):
    data = graphene.List(ActionItemType)
    pagination = graphene.Field(PaginationResponseType)


class TaskViewResponseType(graphene.ObjectType):
    data = graphene.List(TaskViewType)


class PendingItemsResponseType(graphene.ObjectType):
    data = graphene.List(ActionItemType)


class ActionItemListResponseType(graphene.ObjectType):
    data = graphene.List(ActionItemType)


class CalendarActionItemType(graphene.ObjectType):
    date = graphene.String()
    has_items = graphene.Boolean()


class CalendarActionItemResponseType(graphene.ObjectType):
    data = graphene.List(CalendarActionItemType)


class QuickLinkType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    total = graphene.Int()
    data_number = graphene.Int()


class FrameworkCardType(graphene.ObjectType):
    id = graphene.String()
    framework_name = graphene.String()
    controls = graphene.Int()
    operational = graphene.Int()
    needs_attention = graphene.Int()
    not_implemented = graphene.Int()
    progress = graphene.Int()
    logo_url = graphene.String()
    sort_index = graphene.Int()

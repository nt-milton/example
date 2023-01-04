import graphene
from django.db.models import Count, Q
from graphene_django.types import DjangoObjectType

from action_item.models import ActionItem, ActionItemStatus
from control.models import ControlGroup
from control.types import ControlType


class ControlGroupType(DjangoObjectType):
    class Meta:
        model = ControlGroup
        fields = (
            'id',
            'name',
            'controls',
            'start_date',
            'due_date',
            'reference_id',
            'sort_order',
        )

    id = graphene.Int()
    progress = graphene.Int()
    controls = graphene.List(ControlType)

    def resolve_id(self, info):
        return self.id

    def resolve_controls(self, info):
        if isinstance(self.controls, list):
            controls: list = []
            for control in self.controls:
                controls.append(control)
            return controls
        return self.controls.all()

    def resolve_progress(self, info, **kwargs):
        summary = ActionItem.objects.filter(
            controls__group=self.id,
            controls__organization=info.context.user.organization,
        ).aggregate(
            total=Count('pk', filter=Q(is_required=True)),
            completed=Count(
                'pk',
                filter=Q(is_required=True)
                & (
                    Q(status=ActionItemStatus.COMPLETED)
                    | Q(status=ActionItemStatus.NOT_APPLICABLE)
                ),
            ),
        )
        return (
            summary['completed'] / summary['total'] * 100 if summary['total'] > 0 else 0
        )

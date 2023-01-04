import graphene

from action_item.constants import TYPE_POLICY
from action_item.models import ActionItem, ActionItemStatus
from dashboard.inputs import UpdateDashboardItemInput
from dashboard.models import ActionItemMetadata
from laika.auth import login_required, permission_required
from laika.decorators import laika_service
from laika.utils.dates import str_date_to_date_formatted
from laika.utils.exceptions import service_exception
from policy.utils.utils import are_policies_completed_by_user


class UpdateDashboardItem(graphene.Mutation):
    class Arguments:
        input = UpdateDashboardItemInput(required=True)

    item = graphene.String()

    @login_required
    @service_exception('Cannot update dashboard item')
    @permission_required('dashboard.view_dashboard')
    def mutate(self, info, input):
        if ActionItemMetadata.objects.filter(
            action_item_id=input.get('unique_action_item_id'),
            assignee=info.context.user,
        ).exists():
            current_item = ActionItemMetadata.objects.get(
                action_item_id=input.get('unique_action_item_id'),
                assignee=info.context.user,
            )
            input.to_model(update=current_item)
            return current_item.action_item_id
        return input.get('unique_action_item_id')


class UpdateDashboardActionItem(graphene.Mutation):
    id = graphene.String()
    seen = graphene.Boolean()
    status = graphene.String()
    completion_date = graphene.Date()
    due_date = graphene.String()

    class Arguments:
        id = graphene.String(required=True)
        seen = graphene.Boolean()
        completion_date = graphene.String()
        action_type = graphene.String()

    @laika_service(
        permission='dashboard.view_dashboard',
        exception_msg='Failed to update user task',
    )
    def mutate(self, info, id, **kwargs):
        user = info.context.user
        action_item = ActionItem.objects.get(id=id, assignees=user)
        needs_update = False
        if kwargs.get('seen'):
            action_item.metadata['seen'] = kwargs.get('seen')
            needs_update = True
        if kwargs.get('completion_date'):
            action_item.completion_date = str_date_to_date_formatted(
                kwargs.get('completion_date')
            )
            action_item.status = ActionItemStatus.COMPLETED
            needs_update = True
        if needs_update:
            action_item.save()

        if kwargs.get('action_type') == TYPE_POLICY and kwargs.get('completion_date'):
            policies_reviewed = are_policies_completed_by_user(user)

            # If the value is the same the user don't need to be updated
            if user.policies_reviewed != policies_reviewed:
                user.policies_reviewed = policies_reviewed
                user.save()

        return UpdateDashboardActionItem(
            id=action_item.id,
            seen=action_item.metadata.get('seen', False),
            status=action_item.status,
            completion_date=action_item.completion_date,
            due_date=action_item.due_date,
        )

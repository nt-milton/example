from django.contrib import admin
from reversion.admin import VersionAdmin

from .forms import TaskForm
from .models import ActionItem, ActionItemMetadata, Task, UserTask


class ActionItemAdmin(VersionAdmin):
    list_display = (
        'organization',
        'type',
        'assignee',
        'due_date',
        'completed_on',
        'status',
        'description',
        'group',
    )

    list_filter = (
        'organization',
        'assignee',
    )

    readonly_fields = [
        'organization',
        'type',
        'assignee',
        'due_date',
        'description',
        'completed_on',
        'status',
        'unique_action_item_id',
        'reference_url',
    ]


admin.site.register(ActionItem, ActionItemAdmin)


class ActionItemMetadataAdmin(VersionAdmin):
    list_display = ('seen', 'action_item_id', 'assignee')
    list_filter = ('assignee',)
    readonly_fields = ['seen', 'action_item_id']


admin.site.register(ActionItemMetadata, ActionItemMetadataAdmin)


class TaskAdmin(VersionAdmin):
    list_display = ('name', 'description', 'task_type', 'task_subtype', 'created_at')
    list_filter = ('task_type',)
    form = TaskForm


admin.site.register(Task, TaskAdmin)


class UserTaskAdmin(VersionAdmin):
    list_display = (
        'assignee',
        'organization',
        'task',
        'seen',
        'completed_on',
        'due_date',
        'status',
    )
    list_filter = ('assignee', 'organization')
    autocomplete_fields = ('organization', 'assignee')


admin.site.register(UserTask, UserTaskAdmin)

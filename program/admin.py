from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import (
    ArchivedEvidence,
    ArchivedProgram,
    ArchivedSubtask,
    ArchivedTask,
    ArchivedUser,
    Program,
    SubTask,
    SubtaskCertificationSection,
    SubtaskTag,
    Task,
    TaskComment,
)


class ProgramAdmin(VersionAdmin):
    model = Program
    list_display = (
        'name',
        'organization',
        'description',
        'documentation_link',
        'static_icon',
        'animated_icon',
        'created_at',
    )
    list_filter = ('organization',)


admin.site.register(Program, ProgramAdmin)


class SubTaskInlineAdmin(admin.TabularInline):
    model = SubTask


class TaskCommentInlineAdmin(admin.TabularInline):
    model = TaskComment
    fields = ['owner', 'content']
    readonly_fields = ['owner', 'content']

    def owner(self, instance):
        return instance.comment.owner_name

    def content(self, instance):
        return instance.comment.content

    classes = ['collapse']


class TaskAdmin(VersionAdmin):
    list_display = ('name', 'program', 'category', 'tier', 'created_at')
    list_filter = ('program__organization', 'program')

    inlines = [TaskCommentInlineAdmin]


admin.site.register(Task, TaskAdmin)


class SubtaskTagInlineAdmin(admin.StackedInline):
    model = SubtaskTag


class SubtaskCertificationSectionInlineAdmin(admin.StackedInline):
    model = SubtaskCertificationSection


class SubTaskAdmin(VersionAdmin):
    list_display = (
        'get_text',
        'reference_id',
        'assignee',
        'get_group',
        'requires_evidence',
        'sort_index',
        'complexity_group',
        'complexity',
        'due_date',
        'task',
        'get_priority',
        'status',
        'badges',
        'created_at',
    )
    search_fields = ['text', 'reference_id']
    list_filter = ('task__program__organization', 'task__program')
    inlines = [SubtaskTagInlineAdmin, SubtaskCertificationSectionInlineAdmin]


admin.site.register(SubTask, SubTaskAdmin)


class ArchivedTasks(admin.TabularInline):
    model = ArchivedTask
    readonly_fields = ('id', 'name', 'data', 'organization', 'created_at')
    can_delete = False

    def name(self, obj):
        if obj.data:
            return obj.data['name']
        return ''

    def has_add_permission(self, request, obj=None):
        return False


class ArchivedProgramAdmin(VersionAdmin):
    model = ArchivedProgram
    list_display = ('id', 'name', 'organization', 'created_at')
    list_filter = ('organization',)
    inlines = [ArchivedTasks]

    def name(self, obj):
        return obj.data['name']


admin.site.register(ArchivedProgram, ArchivedProgramAdmin)


class ArchivedSubTasks(admin.TabularInline):
    model = ArchivedSubtask
    readonly_fields = ('id', 'description', 'data', 'task', 'created_at')
    can_delete = False

    def description(self, obj):
        if obj.data:
            return obj.data['description']
        return ''

    def has_add_permission(self, request, obj=None):
        return False


class ArchivedTaskAdmin(VersionAdmin):
    model = ArchivedTask
    list_display = ('id', 'name', 'program', 'created_at')
    list_filter = ('program',)
    inlines = [ArchivedSubTasks]

    def name(self, obj):
        return obj.data['name']


admin.site.register(ArchivedTask, ArchivedTaskAdmin)


class ArchivedSubtaskAdmin(VersionAdmin):
    model = ArchivedSubtask
    list_display = ('id', 'description', 'task', 'created_at')
    list_filter = ('task',)

    def description(self, obj):
        return obj.data['description']


admin.site.register(ArchivedSubtask, ArchivedSubtaskAdmin)


class ArchivedEvidenceAdmin(VersionAdmin):
    model = ArchivedEvidence
    list_display = ('name', 'organization', 'type', 'created_at', 'updated_at')
    list_filter = ('organization', 'type')


admin.site.register(ArchivedEvidence, ArchivedEvidenceAdmin)


class ArchivedUserAdmin(VersionAdmin):
    model = ArchivedUser
    list_display = ('first_name', 'last_name', 'email', 'created_at', 'updated_at')


admin.site.register(ArchivedUser, ArchivedUserAdmin)

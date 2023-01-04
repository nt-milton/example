from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import Alumni, Training, TrainingAssignee


class TrainingAdmin(VersionAdmin):
    list_display = ('id', 'name', 'roles', 'category', 'description')
    list_filter = ('organization',)


admin.site.register(TrainingAssignee)
admin.site.register(Training, TrainingAdmin)


class AlumniAdmin(VersionAdmin):
    recover_list_template = "training/alumni/recover_list.html"
    list_display = (
        'created_at',
        'id',
        'user',
        'training',
        'training_category',
        'first_name',
        'last_name',
        'email',
    )
    list_filter = ('training__organization', 'training', 'user')


admin.site.register(Alumni, AlumniAdmin)

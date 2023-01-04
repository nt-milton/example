from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import Report, Template


class ReportAdmin(VersionAdmin):
    model = Report
    list_display = ('display_id', 'name', 'owner', 'created_at', 'updated_at')


class TemplateAdmin(VersionAdmin):
    model = Template
    list_display = ('created_at', 'updated_at', 'name', 'organization')


admin.site.register(Report, ReportAdmin)
admin.site.register(Template, TemplateAdmin)

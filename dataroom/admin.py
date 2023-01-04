from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import Dataroom, DataroomEvidence


class DataroomEvidenceInlineAdmin(admin.StackedInline):
    model = DataroomEvidence


class DataroomAdmin(VersionAdmin):
    model = Dataroom
    list_display = ('name', 'organization', 'owner', 'is_soft_deleted')
    list_filter = ('organization', 'name', 'owner', 'is_soft_deleted')
    inlines = [DataroomEvidenceInlineAdmin]


admin.site.register(Dataroom, DataroomAdmin)

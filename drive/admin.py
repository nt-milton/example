from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import Drive, DriveEvidence, Folder


class DriveEvidenceInlineAdmin(admin.TabularInline):
    model = DriveEvidence


class DriveAdmin(VersionAdmin):
    model = Drive
    list_display = ('organization', 'created_at')
    list_filter = ('organization',)
    inlines = [
        DriveEvidenceInlineAdmin,
    ]


class FolderAdmin(VersionAdmin):
    model = Folder
    list_display = ('name', 'created_at')
    list_filter = ('drive__organization', 'name')


admin.site.register(Folder, FolderAdmin)
admin.site.register(Drive, DriveAdmin)

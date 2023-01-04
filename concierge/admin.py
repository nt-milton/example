from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import ConciergeRequest


class ConciergeRequestAdmin(VersionAdmin):
    list_display = (
        'id',
        'created_at',
        'organization',
        'request_type',
        'created_by',
        'requested_email',
        'status',
    )
    readonly_fields = [
        'requested_email',
    ]
    list_filter = ('status', 'request_type', 'organization')
    ordering = ('-created_at',)


admin.site.register(ConciergeRequest, ConciergeRequestAdmin)

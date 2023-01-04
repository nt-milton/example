from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import Evidence, TagEvidence


class TagEvidenceInlineAdmin(admin.StackedInline):
    model = TagEvidence
    raw_id_fields = ('tag',)


class EvidenceAdmin(VersionAdmin):
    model = Evidence
    list_display = ('name', 'organization', 'type', 'created_at')
    list_filter = ('organization', 'type')
    inlines = [
        TagEvidenceInlineAdmin,
    ]


admin.site.register(Evidence, EvidenceAdmin)

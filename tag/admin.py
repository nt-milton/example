from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import Tag


class TagAdmin(VersionAdmin):
    model = Tag
    list_display = ('name', 'organization')
    list_filter = ('organization', 'created_at')
    search_fields = ('name',)


admin.site.register(Tag, TagAdmin)

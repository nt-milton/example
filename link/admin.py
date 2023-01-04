from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import Link


class LinkAdmin(VersionAdmin):
    model = Link
    list_display = (
        'organization',
        'url',
        'expiration_date',
        'is_enabled',
        'created_at',
        'updated_at',
    )
    list_filter = ('organization', 'is_enabled')


admin.site.register(Link, LinkAdmin)

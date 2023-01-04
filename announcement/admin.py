from django.contrib import admin
from reversion.admin import VersionAdmin

from announcement.models import Announcement

# Register your models here.


class AnnouncementAdmin(VersionAdmin):
    list_display = ('title', 'content', 'url', 'publish_start_date', 'publish_end_date')


admin.site.register(Announcement, AnnouncementAdmin)

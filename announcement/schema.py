from datetime import datetime

from graphene import Field
from pytz import utc

from announcement.models import Announcement
from announcement.types import AnnouncementType
from laika.auth import login_required


class Query(object):
    latest_announcement = Field(AnnouncementType)

    @login_required
    def resolve_latest_announcement(self, info, **kwargs):
        announcement = Announcement.objects.latest('creation_date')
        if (
            announcement.publish_start_date
            < utc.localize(datetime.now())
            < announcement.publish_end_date
        ):
            return announcement
        else:
            return None

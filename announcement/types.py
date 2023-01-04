from datetime import datetime

from graphene import Boolean
from graphene_django.types import DjangoObjectType
from pytz import utc

from announcement.models import Announcement


class AnnouncementType(DjangoObjectType):
    class Meta:
        model = Announcement

    is_active = Boolean()

    def resolve_is_active(self, info):
        return (
            self.publish_start_date
            < utc.localize(datetime.now())
            < self.publish_end_date
        )

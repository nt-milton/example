import logging
from datetime import datetime

import graphene

from laika.auth import login_required, permission_required
from laika.utils.exceptions import service_exception

from .inputs import UpdateLinkInput
from .models import Link

logger = logging.getLogger('link')


class UpdateLink(graphene.Mutation):
    class Arguments:
        input = UpdateLinkInput(required=True)

    id = graphene.String()

    @login_required
    @service_exception('Cannot update the link')
    @permission_required('link.change_link')
    def mutate(self, info, input):
        link = Link.objects.get(
            id=input.link_id, organization=info.context.user.organization
        )
        expiration_date = input.get('expiration_date', '')
        is_enabled = input.get('is_enabled', link.is_enabled)
        link.time_zone = input.get('time_zone', link.time_zone)
        link.is_enabled = is_enabled

        if expiration_date:
            expiration_date = datetime.combine(expiration_date, datetime.min.time())
            link.expiration_date = expiration_date
            link.is_enabled = True
        if expiration_date is None:
            link.expiration_date = None
        link.save()

        return UpdateLink(id=link.id)

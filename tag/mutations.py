import logging

import graphene

from laika.backends.concierge_backend import ConciergeAuthenticationBackend
from laika.backends.laika_backend import AuthenticationBackend
from laika.decorators import service
from laika.utils.get_organization_by_user_type import get_organization_by_user_type
from tag.inputs import AddManualTagInput
from tag.models import Tag

logger = logging.getLogger('tag_mutations')


class AddManualTag(graphene.Mutation):
    class Arguments:
        input = AddManualTagInput(required=True)

    tag_id = graphene.String()

    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'drive.view_driveevidence',
            },
        ],
        exception_msg='Failed to add tag. Please Try again',
    )
    def mutate(self, info, input):
        organization = get_organization_by_user_type(
            info.context.user, input.organization_id
        )
        tag, created = Tag.objects.get_or_create(
            name=input.get('name'),
            organization=organization,
            defaults={'is_manual': input.get('is_manual')},
        )

        if created:
            return AddManualTag(tag.id)

        return AddManualTag()

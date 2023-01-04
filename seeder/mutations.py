import logging

import graphene

from laika.decorators import concierge_service
from seeder.tasks import seed_profiles_to_organization

logger = logging.getLogger(__name__)


class SeedOrganization(graphene.Mutation):
    class Arguments:
        organization_id = graphene.String(required=True)
        profile_ids = graphene.List(graphene.String, required=True)

    success = graphene.Boolean()

    @concierge_service(
        atomic=False,
        permission='user.view_concierge',
        exception_msg='Failed to seed organization',
    )
    def mutate(self, info, **kwargs):
        seed_profiles_to_organization.delay(
            user_id=info.context.user.id,
            organization_id=kwargs.get('organization_id'),
            profile_ids=kwargs.get('profile_ids'),
        )

        return SeedOrganization(success=True)

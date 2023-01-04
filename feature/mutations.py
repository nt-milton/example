import logging
from multiprocessing.pool import ThreadPool

import graphene

from feature.inputs import UpdateFeatureInput
from feature.models import Flag
from feature.tasks import broadcast_features_notification
from feature.types import FeatureFlagType
from laika.decorators import concierge_service
from organization.models import Organization

pool = ThreadPool()
logger = logging.getLogger(__name__)


class UpdateFeature(graphene.Mutation):
    class Arguments:
        input = UpdateFeatureInput(required=True)

    flags = graphene.List(FeatureFlagType)

    @concierge_service(
        permission='user.change_concierge',
        exception_msg='Failed to update feature',
        revision_name='Can view concierge',
    )
    def mutate(self, info, input):
        updated_flags = []
        organization_id = input.get('organization_id')
        flags = input.get('flags')
        updated_data = False

        for ff in flags:
            flag, _ = Flag.objects.get_or_create(
                name=ff.name, organization=Organization.objects.get(id=organization_id)
            )

            if flag.is_enabled != ff.is_enabled:
                updated_data = True

            flag.is_enabled = ff.is_enabled
            flag.save()
            updated_flags.append(
                dict(
                    name=ff.name,
                    is_enabled=ff.is_enabled,
                    organization=flag.organization,
                )
            )
        if updated_data:
            pool.apply_async(
                broadcast_features_notification, args=(info, organization_id)
            )

        return UpdateFeature(updated_flags)

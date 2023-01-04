import logging

import graphene

from laika.decorators import concierge_service
from laika.utils.exceptions import ServiceException
from organization.models import Organization
from seeder.models import MyComplianceMigration, Seed, SeedProfile
from seeder.mutations import SeedOrganization
from seeder.types import (
    MigrationHistoryType,
    SeedOrganizationResponseType,
    SeedProfileResponseType,
    SeedResponseType,
)

logger = logging.getLogger(__name__)


class Mutation(graphene.ObjectType):
    seed_organization = SeedOrganization.Field()


class Query(object):
    seed_profiles = graphene.List(SeedProfileResponseType)
    seed_organization = graphene.Field(
        SeedOrganizationResponseType,
        organization_id=graphene.UUID(required=True),
        profile_id=graphene.UUID(required=True),
    )
    organization_seeds = graphene.List(
        SeedResponseType, id=graphene.UUID(required=True)
    )
    migration_history = graphene.List(
        MigrationHistoryType, id=graphene.UUID(required=True)
    )

    @concierge_service(
        atomic=False,
        permission='user.view_concierge',
        exception_msg='Failed to get seed profiles',
    )
    def resolve_seed_profiles(self, info, **kwargs):
        return SeedProfile.objects.filter(is_visible=True).order_by('name')

    @concierge_service(
        atomic=False,
        permission='user.view_concierge',
        exception_msg='Failed to seed organization',
    )
    def resolve_seed_organization(self, info, **kwargs):
        error = None
        try:
            profile = SeedProfile.objects.get(id=kwargs.get('profile_id'))

            organization = Organization.objects.get(id=kwargs.get('organization_id'))

            if not profile and not organization:
                error = (
                    f'Error resolving seed organization for {profile.name},'
                    f' organization: {organization}'
                )
                logger.error(error)
                raise ServiceException('Invalid request')

            Seed.objects.create(
                organization=organization,
                profile=profile,
                seed_file=profile.file,
                created_by=info.context.user,
            ).run(run_async=True, should_send_alerts=True)

            return SeedOrganizationResponseType(success=True, error=error)
        except Exception:
            return SeedOrganizationResponseType(success=False, error=error)

    @concierge_service(
        atomic=False,
        permission='user.view_concierge',
        exception_msg='Failed to get organization seeds',
    )
    def resolve_organization_seeds(self, info, **kwargs):
        return Seed.objects.filter(organization=kwargs.get('id')).order_by(
            '-created_at'
        )

    @concierge_service(
        atomic=False,
        permission='control.can_migrate_to_my_compliance',
        exception_msg='Failed to get migration history data',
    )
    def resolve_migration_history(self, info, **kwargs):
        return MyComplianceMigration.objects.filter(
            organization__id=kwargs.get('id')
        ).order_by('-created_at')

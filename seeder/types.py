import graphene
from graphene_django import DjangoObjectType

from laika.types import ErrorType
from organization.types import OrganizationType
from seeder.constants import SEED_STATUS
from seeder.models import MyComplianceMigration, Seed, SeedProfile
from user.types import UserType


class SeedProfileResponseType(DjangoObjectType):
    class Meta:
        model = SeedProfile
        fields = (
            'id',
            'name',
            'type',
            'created_at',
            'updated_at',
            'content_description',
            'default_base',
        )

    file = graphene.String()
    type = graphene.String()

    def resolve_file(self, info):
        return self.file.url if self.file else ''

    def resolve_type(self, info):
        return '' if not self.type else self.type


class SeedResponseType(graphene.ObjectType):
    class Meta:
        model = Seed

    id = graphene.String()
    created_at = graphene.DateTime()
    created_by = graphene.Field(UserType)
    organization = graphene.Field(OrganizationType)
    profile = graphene.Field(SeedProfileResponseType)
    status = graphene.String()
    status_detail = graphene.String()
    content_description = graphene.String()

    def resolve_status(self, info, **kwargs):
        return dict(SEED_STATUS)[self.status]


class SeedOrganizationResponseType(graphene.ObjectType):
    success = graphene.Boolean()
    error = graphene.Field(ErrorType)


class MigrationHistoryType(graphene.ObjectType):
    class Meta:
        model = MyComplianceMigration

    id = graphene.String()
    created_at = graphene.DateTime()
    created_by = graphene.Field(UserType)
    status = graphene.String()
    mapped_subtasks = graphene.String()
    frameworks_detail = graphene.String()

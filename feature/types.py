import graphene
from graphene_django.types import DjangoObjectType

from feature.models import AuditorFlag, Flag


class FlagType(DjangoObjectType):
    class Meta:
        model = Flag


class AuditorFlagType(DjangoObjectType):
    class Meta:
        model = AuditorFlag


class FeatureFlagType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    display_name = graphene.String()
    is_enabled = graphene.Boolean()

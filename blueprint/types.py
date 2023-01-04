from enum import Enum

import graphene
from graphene_django import DjangoObjectType

from blueprint.models.control import ControlBlueprint
from blueprint.models.control_family import ControlFamilyBlueprint
from blueprint.models.history import BlueprintHistory
from certification.models import Certification
from certification.types import LogoType
from control.models import Control
from control.types import ControlCertificationType
from laika.types import PaginationResponseType


class ControlBlueprintFilterFields(Enum):
    Frameworks = 'frameworks'
    Families = 'families'
    Status = 'status'


class ControlBlueprintFilterType(graphene.InputObjectType):
    field = graphene.String()
    values = graphene.List(graphene.String)


class ControlFamilyBlueprintType(DjangoObjectType):
    class Meta:
        model = ControlFamilyBlueprint
        fields = ('id', 'name', 'acronym', 'description', 'illustration')


class ControlBlueprintType(DjangoObjectType):
    class Meta:
        model = ControlBlueprint
        fields = (
            'id',
            'reference_id',
            'name',
            'description',
        )

    is_prescribed = graphene.Boolean()
    all_certifications = graphene.List(ControlCertificationType)
    family = graphene.Field(ControlFamilyBlueprintType)

    def resolve_is_prescribed(self, info, **kwargs):
        return Control.objects.filter(
            organization_id=info.variable_values.get('organizationId'),
            reference_id=self.reference_id,
        ).exists()

    def resolve_all_certifications(self, info):
        certifications = Certification.objects.filter(
            sections__controls_blueprint=self
        ).distinct()

        return [
            ControlCertificationType(
                id=certification.id,
                display_name=certification.name,
                logo=LogoType(id=certification.logo.name, url=certification.logo.url)
                if certification.logo
                else None,
            )
            for certification in certifications
        ]

    def resolve_family(self, info):
        return self.family


class BlueprintHistoryType(DjangoObjectType):
    class Meta:
        model = BlueprintHistory
        fields = (
            'id',
            'upload_action',
            'content_description',
            'created_by',
            'created_at',
            'status',
        )


class BlueprintControlsResponseType(graphene.ObjectType):
    data = graphene.List(ControlBlueprintType)
    pagination = graphene.Field(PaginationResponseType)


class AllBlueprintControlsResponseType(graphene.ObjectType):
    data = graphene.List(ControlBlueprintType)


class AllBlueprintHistoryResponseType(graphene.ObjectType):
    blueprint_data_entries = graphene.List(BlueprintHistoryType)

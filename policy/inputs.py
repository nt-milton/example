import graphene
from graphene import InputObjectType

from laika import types
from policy.models import Policy
from tag.inputs import InputTagType


class OnboardingPolicyInput(graphene.InputObjectType):
    id = graphene.Int(required=True)
    use_laika_template = graphene.Boolean()
    file = graphene.Field(types.InputFileType)


class ReplacePolicyInput(graphene.InputObjectType):
    id = graphene.UUID(required=True)
    draft = graphene.Field(types.InputFileType)


class UpdateIsDraftEditedInput(graphene.InputObjectType):
    id = graphene.UUID(required=True)


class UpdateNewPolicyInput(InputObjectType):
    class InputMeta:
        model = Policy

    id = graphene.String(required=True)
    owner = graphene.String()
    approver = graphene.String()
    name = graphene.String()
    description = graphene.String()
    tags = graphene.List(InputTagType)
    is_required = graphene.Boolean()
    is_visible_in_dataroom = graphene.Boolean()

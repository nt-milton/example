from enum import Enum

import graphene
from django.db.models import Max
from graphene_django.types import DjangoObjectType

from control.models import Control
from control.types import ControlType
from laika import types
from laika.types import FileType
from laika.utils.office import export_document_url
from laika.utils.permissions import map_permissions
from user.types import UserType

from .models import OnboardingPolicy, Policy, PublishedPolicy


class PolicyTypes(Enum):
    POLICY = 'Policy'
    PROCEDURE = 'Procedure'


class OnboardingPolicyType(DjangoObjectType):
    class Meta:
        model = OnboardingPolicy

    file = graphene.Field(types.FileType)

    def resolve_file(self, info):
        if not self.file:
            return None

        return types.FileType(
            id=self.file.id, name=self.file.name, url=self.file.file.url
        )

    description = graphene.String()

    def resolve_description(self, info):
        return self.description


class PublishedPolicyType(DjangoObjectType):
    class Meta:
        model = PublishedPolicy

    version = graphene.String()
    is_latest_version = graphene.Boolean()
    contents = graphene.Field(FileType)

    def resolve_is_latest_version(self, info, **kwargs):
        latest_version = (
            PublishedPolicy.objects.filter(policy=self.policy)
            .aggregate(Max('version'))
            .get('version__max', 0)
        )

        return self.version == latest_version

    def resolve_version(self, info):
        return f'V-{self.version}'


class PolicyType(DjangoObjectType):
    class Meta:
        model = Policy
        convert_choices_to_enum = False

    display_id = graphene.String()
    category = graphene.String()
    draft = graphene.Field(FileType)
    permissions = graphene.List(graphene.String)
    owner_details = graphene.Field(UserType)
    published_policy = graphene.Field(PublishedPolicyType)
    published_policy_pdf_url = graphene.String()
    tags = graphene.List(graphene.String, required=False)
    users_count = graphene.Int(default_value=0)
    controls = graphene.List(ControlType)

    def resolve_display_id(self, info):
        return f'P-{self.display_id}'

    def resolve_owner_details(self, info):
        return self.owner

    def resolve_permissions(self, info):
        return map_permissions(info.context.user, 'policy')

    def resolve_published_policy(self, info):
        if not self.is_published:
            return None
        return self.versions.latest('version')

    def resolve_tags(self, info):
        return self.policy_tags.all()

    def resolve_published_policy_pdf_url(self, info):
        if not self.is_published:
            return None
        published_policy = self.versions.latest('version')
        return export_document_url(
            published_policy.published_key,
            published_policy.policy.name,
            published_policy.contents.url,
        )

    def resolve_users_count(self, info):
        if self.is_required:
            if PublishedPolicy.objects.filter(policy__id=self.id).count() >= 1:
                return self.action_items.filter(metadata__seen=False).count()
            else:
                return self.organization.get_users(
                    only_laika_users=True, exclude_super_admin=True
                ).count()

        return 0

    def resolve_controls(self, info):
        if not self.control_family:
            return []
        return Control.objects.filter(
            pillar=self.control_family, organization=self.organization
        )


class FiltersPolicyType(graphene.InputObjectType):
    search = graphene.String()
    owner = graphene.List(graphene.String)
    category = graphene.List(graphene.String)
    control_family = graphene.List(graphene.String)
    type = graphene.List(graphene.String)
    is_published = graphene.List(graphene.String)
    tags = graphene.List(graphene.String)

import graphene
from graphene_django.types import DjangoObjectType

from action_item.models import ActionItem, ActionItemStatus
from certification.helpers import get_certification_progress
from certification.models import (
    Certification,
    CertificationSection,
    UnlockedOrganizationCertification,
)
from laika.types import FileType


class LogoType(graphene.ObjectType):
    id = graphene.String()
    url = graphene.String()


class CertificateType(DjangoObjectType):
    class Meta:
        model = Certification

    logo_file = graphene.Field(LogoType)
    progress = graphene.Int(default_value=0)
    is_locked = graphene.Boolean(default_value=False)

    def resolve_logo_file(self, info):
        if self.logo:
            return LogoType(id=self.logo.name, url=self.logo.url)
        return None

    def resolve_progress(self, info, **kwargs):
        program_loader = info.context.loaders.program
        return program_loader.certificate_progress.load(self.id)

    def resolve_is_locked(self, info, **kwargs):
        organization = info.context.user.organization
        unlocked_cert = UnlockedOrganizationCertification.objects.filter(
            organization=organization, certification=self
        ).exists()
        return not unlocked_cert


class CertificationType(DjangoObjectType):
    class Meta:
        model = Certification

    url = graphene.String()
    logo = graphene.Field(FileType)

    def resolve_id(self, info):
        return self.id

    def resolve_logo(self, info):
        return self.logo or None


class UnlockedOrganizationCertificationType(DjangoObjectType):
    class Meta:
        model = UnlockedOrganizationCertification
        fields = ('id', 'target_audit_start_date', 'target_audit_completion_date')

    target_audit_start_date = graphene.DateTime()
    target_audit_completion_date = graphene.DateTime()
    certification = graphene.Field(CertificationType)


class LockedCertificationsType(DjangoObjectType):
    class Meta:
        model = Certification

    logo_file = graphene.Field(LogoType)
    progress = graphene.Int()
    is_locked = graphene.Boolean(default_value=False)

    def resolve_logo_file(self, info):
        if self.logo:
            return LogoType(id=self.logo.name, url=self.logo.url)
        return None

    def resolve_is_locked(self, info):
        # TODO: this resolve returns always true because the service was
        # changed to always return just the locked certifications for
        # the organization. But the field is still required on FE.
        # To remove this resolve, eliminate the isLocked variable for
        # certifications on FE.
        return True

    def resolve_progress(self, info):
        organization = info.context.user.organization
        required_action_items_completed = ActionItem.objects.filter(
            controls__certification_sections__certification=self,
            controls__organization=organization,
            status__in=[ActionItemStatus.COMPLETED, ActionItemStatus.NOT_APPLICABLE],
            is_required=True,
        ).distinct()

        return get_certification_progress(
            required_action_items_completed.count(), self.required_action_items
        )


class CertificationSectionType(DjangoObjectType):
    class Meta:
        model = CertificationSection
        fields = ("id",)

    full_name = graphene.String()


class CertificationProgressPerUser(graphene.ObjectType):
    id = graphene.String()
    progress = graphene.Int(default_value=0)
    user_id = graphene.String()

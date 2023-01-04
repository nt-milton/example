import graphene

from audit.models import AuditorAuditFirm
from feature.mutations import UpdateFeature
from feature.types import AuditorFlagType, FeatureFlagType, FlagType
from laika.auth import login_required
from laika.decorators import audit_service, concierge_service
from laika.utils.exceptions import service_exception

from .constants import DEFAULT_ORGANIZATION_FEATURE_FLAGS
from .models import AuditorFlag, Flag


class Mutation(object):
    update_feature = UpdateFeature.Field()


def get_flags(info, **kwargs):
    organization_id = kwargs.get('organization_id')
    org_id = organization_id

    flags = []

    if organization_id or info.context.user.organization:
        organization_flags = Flag.objects.filter(
            organization__id=org_id if org_id else info.context.user.organization.id
        )

        for ff in organization_flags:
            flags.append(dict(name=ff.name, is_enabled=ff.is_enabled))

    return flags


class Query(object):
    all_feature_flags = graphene.List(FeatureFlagType)
    flags = graphene.List(FeatureFlagType, organization_id=graphene.UUID())
    cx_flags = graphene.List(FeatureFlagType, organization_id=graphene.UUID())
    flag = graphene.Field(FeatureFlagType, name=graphene.String())

    auditor_flags = graphene.List(FeatureFlagType)
    auditor_flag = graphene.Field(FeatureFlagType, name=graphene.String())

    @concierge_service(
        permission='user.view_concierge',
        exception_msg='Failed to get feature flags list',
        revision_name='Can view concierge',
    )
    def resolve_all_feature_flags(self, info, **kwargs):
        flags = []
        for feature_flag in DEFAULT_ORGANIZATION_FEATURE_FLAGS.values():
            flags.append(feature_flag)
        return flags

    @login_required
    @service_exception('Cannot get flags for organization')
    def resolve_flags(self, info, **kwargs):
        return get_flags(info, **kwargs)

    @concierge_service(
        permission='user.view_concierge',
        exception_msg='Failed to get organization flags',
        revision_name='Can view concierge',
    )
    def resolve_cx_flags(self, info, **kwargs):
        return get_flags(info, **kwargs)

    @login_required
    @service_exception('Cannot get flag by name')
    def resolve_flag(self, info, **kwargs):
        try:
            return Flag.objects.get(
                organization=info.context.user.organization, name=kwargs.get('name')
            )
        except Flag.DoesNotExist:
            return FlagType(
                name=kwargs.get('name'),
                organization=info.context.user.organization,
                is_enabled=False,
            )

    @audit_service(
        permission='audit.view_audit',
        exception_msg='Failed to get auditor feature flag',
    )
    def resolve_auditor_flag(self, info, **kwargs):
        user = info.context.user
        auditor_audit_firm = AuditorAuditFirm.objects.filter(auditor__user=user).first()
        try:
            return AuditorFlag.objects.get(
                audit_firm=auditor_audit_firm.audit_firm, name=kwargs.get('name')
            )
        except AuditorFlag.DoesNotExist:
            return AuditorFlagType(name=kwargs.get('name'), is_enabled=False)

    @audit_service(
        permission='audit.view_audit',
        exception_msg='Failed to get auditor feature flags list',
    )
    def resolve_auditor_flags(self, info):
        user = info.context.user
        audit_firm = None
        auditor_audit_firm = AuditorAuditFirm.objects.filter(auditor__user=user).first()

        if auditor_audit_firm:
            audit_firm = auditor_audit_firm.audit_firm.id

        return AuditorFlag.objects.filter(audit_firm=audit_firm)

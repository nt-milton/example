import logging
from multiprocessing.pool import ThreadPool

import graphene
from django.db.models import Q, Value
from django.db.models.functions import Concat

import certification.errors as errors
from certification.helpers import (
    certification_action_items_per_user_query,
    certification_required_action_items_completed_query,
    certification_required_action_items_query,
    unlocked_certifications_progress_annotate,
)
from certification.inputs import UnlockedOrganizationCertificationInput
from certification.models import (
    Certification,
    CertificationSection,
    UnlockedOrganizationCertification,
)
from certification.mutations import (
    UpdateAuditCompletionDate,
    UpdateAuditDatesUnlockedOrgCertification,
)
from certification.tasks import broadcast_frameworks_notification
from certification.types import (
    CertificateType,
    CertificationProgressPerUser,
    CertificationSectionType,
    LockedCertificationsType,
    UnlockedOrganizationCertificationType,
)
from control.constants import SEED_PROFILES_MAPPING
from laika.decorators import concierge_service, laika_service
from laika.types import BaseResponseType, ErrorType
from organization.models import Organization

pool = ThreadPool()
logger = logging.getLogger(__name__)


def get_organization_certificates_by_id(organization_id):
    certifications = UnlockedOrganizationCertification.objects.filter(
        organization__id=organization_id
    ).order_by('certification__sort_index')

    return UnlockedOrganizationCertificationResponseType(data=certifications)


class UnlockedOrganizationCertificationResponseType(BaseResponseType):
    data = graphene.List(UnlockedOrganizationCertificationType)


class Query(object):
    certification_list = graphene.List(CertificateType)
    compliance_certification_list = graphene.List(CertificateType)
    # TODO: Refactor name to match CX Application
    # This query is meant to be used only within a Concierge Service decorator
    certifications_by_organization = graphene.Field(
        UnlockedOrganizationCertificationResponseType, id=graphene.UUID(required=True)
    )
    # TODO: Refactor name to match Laika Web
    # This query is meant to be used only within a Laika Service decorator
    all_certifications_by_organization = graphene.Field(
        UnlockedOrganizationCertificationResponseType
    )
    # This resolve returns only locked certifications for the organization
    all_certification_list = graphene.List(LockedCertificationsType)

    certifications_for_playbooks_migration = graphene.List(CertificateType)

    unlocked_certification_sections = graphene.List(CertificationSectionType)
    unlocked_certification_progress_per_user = graphene.Field(
        CertificationProgressPerUser, id=graphene.ID(required=True)
    )

    @concierge_service(
        permission='user.view_concierge',
        exception_msg='Failed to retrieve the certification list',
        revision_name='Can view concierge',
    )
    def resolve_certification_list(self, info):
        return Certification.objects.filter(is_visible=True).order_by(
            'sort_index', 'name'
        )

    @concierge_service(
        permission='user.view_concierge',
        exception_msg='Failed to retrieve my compliance certification list',
    )
    def resolve_certifications_for_playbooks_migration(self, info):
        return Certification.objects.filter(
            name__in=SEED_PROFILES_MAPPING.keys()
        ).order_by('sort_index', 'name')

    @concierge_service(
        permission='user.view_concierge',
        exception_msg='Failed to retrieve my compliance certification list',
    )
    def resolve_compliance_certification_list(self, info):
        return Certification.objects.filter(
            is_visible=True,
            code__isnull=False,
            code__gt='',
            airtable_record_id__isnull=False,
            airtable_record_id__gt='',
        ).order_by('sort_index', 'name')

    @concierge_service(
        permission='user.view_concierge',
        exception_msg='''
        Failed to retrieve the certification list by organization
        ''',
        revision_name='Can view concierge',
    )
    def resolve_certifications_by_organization(self, info, **kwargs):
        return get_organization_certificates_by_id(kwargs.get('id'))

    @laika_service(
        permission='program.view_program',
        exception_msg='''
        Failed to get organization certificates. Please try again.
        ''',
        revision_name='Can view concierge',
    )
    def resolve_all_certifications_by_organization(self, info, **kwargs):
        return get_organization_certificates_by_id(info.context.user.organization_id)

    @laika_service(
        permission='program.view_program',
        exception_msg='''
        Failed to get organization certificates. Please try again.
        ''',
        revision_name='Can view concierge',
    )
    def resolve_all_certification_list(self, info, **kwargs):
        # TODO: this resolve returns locked certifications for the organization
        # resolve name was not change due that we do not have to change the service
        # name on FE. This name can be changed later to resolve_locked_certifications
        organization = info.context.user.organization
        unlocked_certification_ids = organization.unlocked_certifications.values_list(
            'certification__id', flat=True
        )

        certifications = Certification.objects.filter(
            ~Q(id__in=unlocked_certification_ids), required_action_items__gt=0
        )

        return certifications

    @laika_service(
        permission='control.view_control',
        exception_msg='''
        Failed to get certification sections. Please try again.
        ''',
        revision_name='Can view concierge',
    )
    def resolve_unlocked_certification_sections(self, info):
        organization = info.context.user.organization
        unlock_certifications = (
            UnlockedOrganizationCertification.objects.filter(organization=organization)
            .values_list('certification_id', flat=True)
            .distinct()
        )

        return (
            CertificationSection.objects.filter(
                certification__in=list(unlock_certifications)
            )
            .select_related("certification")
            .annotate(full_name=Concat('certification__name', Value('-'), 'name'))
        )

    @laika_service(
        permission='program.view_program',
        exception_msg='Failed to get certification         progress for user',
    )
    def resolve_unlocked_certification_progress_per_user(self, info, **kwargs):
        user = info.context.user
        organization = info.context.user.organization
        certification_id = kwargs.get('id')
        total_action_items_query = certification_required_action_items_query(
            organization.id
        ) & certification_action_items_per_user_query(user)
        completed_action_items_query = (
            certification_required_action_items_completed_query()
        )
        unlocked_certification = (
            UnlockedOrganizationCertification.objects.filter(
                organization=organization, certification_id=certification_id
            )
            .annotate(
                **unlocked_certifications_progress_annotate(
                    total_action_items_query, completed_action_items_query
                )
            )
            .first()
        )

        return CertificationProgressPerUser(
            id=unlocked_certification.certification_id,
            progress=unlocked_certification.progress,
            user_id=user.id,
        )


class UpdateUnlockedOrgCertification(graphene.Mutation):
    class Arguments:
        input = UnlockedOrganizationCertificationInput(required=True)

    success = graphene.Boolean()
    error = graphene.Field(ErrorType)

    @concierge_service(
        permission='user.change_concierge',
        exception_msg='Failed to unlock certification',
        revision_name='Can update concierge',
    )
    def mutate(self, info, input):
        success = True
        error = None
        try:
            organization_id = input.get('organization_id')
            certifications = input.get('certifications')

            organization = Organization.objects.get(id=organization_id)
            updated_data = False
            for cert in certifications:
                certification = Certification.objects.get(id=cert.certification_id)

                cert_exists = UnlockedOrganizationCertification.objects.filter(
                    organization=organization,
                    certification=certification,
                ).exists()

                if cert.is_unlocking and not cert_exists:
                    UnlockedOrganizationCertification.objects.create(
                        organization=organization,
                        certification=certification,
                    )
                    updated_data = True
                if not cert.is_unlocking and cert_exists:
                    UnlockedOrganizationCertification.objects.filter(
                        organization=organization,
                        certification=certification,
                    ).delete()
                    updated_data = True

            if updated_data:
                pool.apply_async(
                    broadcast_frameworks_notification, args=(info, organization_id)
                )

            return UpdateUnlockedOrgCertification(success=success, error=error)
        except Exception as e:
            logger.warning(f'Error updating feature flags: {e}')
            return UpdateUnlockedOrgCertification(
                success=False, error=errors.UPDATE_UNLOCK_CERTIFICATION_ERROR
            )


class Mutation(graphene.ObjectType):
    update_unlock_certification = UpdateUnlockedOrgCertification.Field()
    update_audit_dates_unlocked_org_certification = (
        UpdateAuditDatesUnlockedOrgCertification.Field()
    )
    update_audit_completion_date = UpdateAuditCompletionDate.Field()

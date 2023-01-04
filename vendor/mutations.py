import json
import logging

import graphene
import reversion
from django.db import transaction

from alert.constants import ALERT_TYPES_DISCOVERY
from alert.models import Alert
from laika.auth import login_required, permission_required
from laika.decorators import laika_service
from laika.utils.exceptions import GENERIC_FILES_ERROR_MSG, service_exception
from laika.utils.history import create_revision
from user.models import User
from vendor.models import (
    ACTIVE_DISCOVERY_STATUSES,
    ALERTS_USER_ROLES,
    DISCOVERY_STATUS_CONFIRMED,
    DISCOVERY_STATUS_IGNORED,
    OrganizationVendor,
    VendorCandidate,
)

from .evidence_handler import (
    add_vendor_officers,
    add_vendor_other_evidence,
    add_vendor_policy,
    add_vendor_teams,
    delete_evidence,
    upload_vendor_file,
)
from .inputs import (
    AddOrganizationVendorDocumentsInput,
    DeleteOrganizationVendorDocumentsInput,
)

logger = logging.getLogger('vendor_mutations')


class ConfirmVendorCandidates(graphene.Mutation):
    class Arguments:
        confirmed_vendor_ids = graphene.List(graphene.NonNull(graphene.ID))
        ignored_vendor_ids = graphene.List(graphene.NonNull(graphene.ID))

    vendor_ids = graphene.List(graphene.NonNull(graphene.ID))

    @laika_service(
        permission='vendor.add_organizationvendor',
        exception_msg='Failed to confirm vendor candidate',
    )
    def mutate(self, info, confirmed_vendor_ids, ignored_vendor_ids):
        organization = info.context.user.organization
        receivers = User.objects.filter(
            organization=organization, role__in=ALERTS_USER_ROLES
        )
        receivers_ids = [receiver.id for receiver in receivers]
        Alert.objects.filter(
            receiver_id__in=receivers_ids,
            type=ALERT_TYPES_DISCOVERY['VENDOR_DISCOVERY'],
        ).delete()
        valid_vendor_candidates_for_vendors = VendorCandidate.objects.filter(
            status__in=ACTIVE_DISCOVERY_STATUSES, vendor__id__in=confirmed_vendor_ids
        )
        vendor_ids = []
        for vendor_candidate in valid_vendor_candidates_for_vendors:
            _, created = OrganizationVendor.objects.get_or_create(
                vendor=vendor_candidate.vendor, organization=organization
            )
            if created:
                vendor_ids.append(vendor_candidate.vendor.id)
        VendorCandidate.objects.filter(
            vendor__id__in=ignored_vendor_ids,
            organization=organization,
            status__in=ACTIVE_DISCOVERY_STATUSES,
        ).update(status=DISCOVERY_STATUS_IGNORED)
        VendorCandidate.objects.filter(
            vendor__id__in=vendor_ids,
            organization=organization,
            status__in=ACTIVE_DISCOVERY_STATUSES,
        ).update(status=DISCOVERY_STATUS_CONFIRMED)
        return ConfirmVendorCandidates(vendor_ids=vendor_ids)


class AddVendorDocuments(graphene.Mutation):
    class Arguments:
        input = AddOrganizationVendorDocumentsInput(required=True)

    document_ids = graphene.List(graphene.String)

    @login_required
    @transaction.atomic
    @service_exception(GENERIC_FILES_ERROR_MSG)
    @permission_required('vendor.add_organizationvendorevidence')
    @create_revision('Documents added to vendor')
    def mutate(self, info, input):
        with transaction.atomic():
            organization = info.context.user.organization
            organization_vendor = organization.organization_vendors.get(pk=input.id)
            added_files_ids = upload_vendor_file(
                organization, input.get('uploaded_files', []), organization_vendor
            )
            added_policies_ids = add_vendor_policy(
                organization, input.get('policies', []), organization_vendor
            )
            added_other_evidence_ids = add_vendor_other_evidence(
                organization, input.get('other_evidence', []), organization_vendor
            )
            added_teams_ids = add_vendor_teams(
                organization,
                input.get('teams', []),
                organization_vendor,
                input.time_zone,
            )
            added_officer_ids = add_vendor_officers(
                organization,
                input.get('officers', []),
                organization_vendor,
                input.time_zone,
            )

            document_ids = (
                added_files_ids
                + added_policies_ids
                + added_other_evidence_ids
                + added_teams_ids
                + added_officer_ids
            )

            return AddVendorDocuments(document_ids=document_ids)


class DeleteVendorDocuments(graphene.Mutation):
    class Arguments:
        input = DeleteOrganizationVendorDocumentsInput(required=True)

    success = graphene.Boolean(default_value=True)

    @login_required
    @transaction.atomic
    @service_exception('Failed to delete documents from organization vendor')
    @permission_required('vendor.delete_organizationvendorevidence')
    def mutate(self, info, input):
        organization = info.context.user.organization
        organization_vendor = OrganizationVendor.objects.get(
            id=input.id, organization=organization
        )
        with reversion.create_revision():
            reversion.set_comment('Deleted vendor documents')
            reversion.set_user(info.context.user)

            documents_to_delete = []
            all_documents = json.loads(input.documents[0])

            for document in all_documents:
                documents_to_delete.append(document['id'])
            delete_evidence(organization, documents_to_delete, organization_vendor)

            logger.info(
                f'Vendor evidence ids {documents_to_delete} in '
                f'organization {organization} deleted'
            )
            return DeleteVendorDocuments()

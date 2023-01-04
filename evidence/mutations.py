import logging

import graphene
from django.core.cache import cache
from django.db import transaction

import evidence.constants as constants
from control.models import Control, ControlEvidence
from dataroom.models import Dataroom, DataroomEvidence
from drive.models import Drive, DriveEvidence
from drive.types import DriveEvidenceType
from evidence.evidence_handler import get_strip_file_name, reference_evidence_exists
from evidence.inputs import (
    EvidenceInput,
    ExportRequestInput,
    LinkTagsToEvidenceInput,
    RenameEvidenceInput,
)
from evidence.models import AsyncExportRequest, Evidence, TagEvidence
from laika.backends.concierge_backend import ConciergeAuthenticationBackend
from laika.backends.laika_backend import AuthenticationBackend
from laika.cache import DEFAULT_TIME_OUT
from laika.decorators import laika_service, service
from laika.utils.exceptions import ServiceException
from laika.utils.get_organization_by_user_type import get_organization_by_user_type
from laika.utils.replace import replace_special_char
from tag.models import Tag
from vendor.models import OrganizationVendor, OrganizationVendorEvidence

logger = logging.getLogger('evidence_mutations')


class UpdateEvidence(graphene.Mutation):
    class Arguments:
        input = EvidenceInput(required=True)

    success = graphene.Boolean(default_value=True)

    @laika_service(
        permission='evidence.rename_evidence',
        exception_msg='Failed to update evidence',
        revision_name='Update Evidence',
    )
    def mutate(self, info, input):
        organization = info.context.user.organization

        evidence = Evidence.objects.get(id=input.evidence_id, organization=organization)
        evidence.description = input.description
        evidence.save()
        return UpdateEvidence()


class RenameEvidence(graphene.Mutation):
    class Arguments:
        input = RenameEvidenceInput(required=True)

    evidence = graphene.Field(DriveEvidenceType)

    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'evidence.rename_evidence',
            },
        ],
        exception_msg='Failed to rename document',
        revision_name='Renamed document',
    )
    def mutate(self, info, input):
        organization = get_organization_by_user_type(
            info.context.user, input.organization_id
        )
        evidence = Evidence.objects.get(id=input.evidence_id, organization=organization)
        new_name = get_strip_file_name(evidence.type, input.new_name)
        if len(new_name) > constants.DOCUMENT_NAME_MAX_LENGHT:
            raise ServiceException('Document name is too long.')

        # Raise an exception if the filename already exist.
        try:
            verify_file_is_unique_per_org(
                organization, new_name, input.sender, input.reference_id, evidence
            )
        except ServiceException:
            raise ServiceException('Unable to rename file, file name already exists')

        if evidence.type == constants.POLICY:
            evidence.policy.name = new_name
            evidence.policy.save()

        evidence.name = new_name
        evidence.save()

        return RenameEvidence(evidence=evidence)


class LinkTagsToEvidence(graphene.Mutation):
    class Arguments:
        input = LinkTagsToEvidenceInput(required=True)

    success = graphene.Boolean(default_value=True)

    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'drive.view_driveevidence',
            },
        ],
        exception_msg='Cannot get tags',
        revision_name='Tags linked to evidence',
    )
    def mutate(self, info, input):
        new_manual_tags = input.get('new_manual_tags')
        created_tags = []

        organization = get_organization_by_user_type(
            info.context.user, input.organization_id
        )

        if new_manual_tags:
            created_tags = [
                Tag.objects.create(
                    name=tag,
                    is_manual=True,
                    organization=organization,
                )
                for tag in new_manual_tags
            ]

        tags = Tag.objects.filter(
            id__in=input.get('tag_ids'), organization=organization
        )

        evidence = Evidence.objects.get(
            id=input.get('evidence_id'), organization=organization
        )

        for tag in list(tags) + created_tags:
            if evidence:
                TagEvidence.objects.create(evidence=evidence, tag=tag)

        tags = set(evidence.tags.all())

        cache.set(
            f'manual_tags_for_{organization.id}_{evidence.id}', tags, DEFAULT_TIME_OUT
        )

        cache.set(
            f'tags_filter_{organization.id}',
            organization.drive.evidence.evidence_and_system_tags,
            DEFAULT_TIME_OUT,
        )

        return LinkTagsToEvidence()


class UnlinkTagsToEvidence(graphene.Mutation):
    class Arguments:
        input = LinkTagsToEvidenceInput(required=True)

    success = graphene.Boolean(default_value=True)

    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'drive.view_driveevidence',
            },
        ],
        exception_msg='Cannot get tags',
        revision_name='Tags unlinked to evidence',
    )
    def mutate(self, info, input):
        organization = get_organization_by_user_type(
            info.context.user, input.organization_id
        )
        evidence_id = input.get('evidence_id')

        cache.delete(f'manual_tags_for_{organization.id}_{evidence_id}')

        TagEvidence.objects.filter(
            evidence_id=input.get('evidence_id'), tag_id__in=input.get('tag_ids')
        ).delete()

        cache.set(
            f'tags_filter_{organization.id}',
            organization.drive.evidence.evidence_and_system_tags,
            DEFAULT_TIME_OUT,
        )

        return LinkTagsToEvidence()


def verify_file_is_unique_per_org(
    organization, new_name, sender, reference_id, evidence
):
    exists = False
    # TODO: we should try to refactor this so we don't need to update
    # this everytime a new module uses the rename
    if sender and sender == 'Dataroom':
        dt = Dataroom.objects.get(id=reference_id, organization=organization)
        filters = {'dataroom': dt}
        exists = reference_evidence_exists(
            DataroomEvidence, new_name, evidence.type, filters
        )

    if sender and sender == 'Vendor':
        ov = OrganizationVendor.objects.get(id=reference_id, organization=organization)
        filters = {'organization_vendor': ov}
        exists = reference_evidence_exists(
            OrganizationVendorEvidence, new_name, evidence.type, filters
        )

    if sender and sender == 'Control':
        control = Control.objects.get(id=reference_id, organization=organization)
        filters = {'control': control}
        exists = reference_evidence_exists(
            ControlEvidence, new_name, evidence.type, filters
        )

    if sender and sender == 'Drive':
        exists = reference_evidence_exists(
            DriveEvidence, new_name, evidence.type, {'drive': organization.drive}
        )

    if exists:
        raise ServiceException('Unable to rename file, file name already exists')


class AsyncExport(graphene.Mutation):
    class Arguments:
        input = ExportRequestInput(required=True)

    success = graphene.Boolean(default_value=True)

    @transaction.atomic
    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'evidence.add_asyncexportevidence',
            },
        ],
        exception_msg='Failed to generate async export',
        revision_name='Async export',
    )
    def mutate(self, info, input):
        organization = get_organization_by_user_type(
            info.context.user, input.organization_id
        )
        entity = (
            Dataroom.objects.get(id=input.dataroom_id, organization=organization)
            if input.dataroom_id
            else organization.drive
        )

        evidence = (
            entity.evidence.all()
            if not input.evidence_id
            else Evidence.objects.filter(
                organization=organization, id__in=input.evidence_id
            )
        )

        name = (
            replace_special_char(entity.name)
            if input.export_type == 'DATAROOM' and not isinstance(entity, Drive)
            else f'laika-documents-{replace_special_char(organization.name)}'
        )

        export_request = AsyncExportRequest.objects.create(
            organization=organization,
            requested_by=info.context.user,
            name=name,
            export_type=input.export_type,
        )
        export_request.evidence.set(evidence)
        export_request.save()

        return AsyncExport()

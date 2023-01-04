import io
import logging

import graphene
from django.core.files import File
from django.db import transaction

import evidence.constants as constants
from drive.evidence_handler import create_laika_paper_evidence, upload_drive_file
from drive.tasks import delete_evidences_from_s3, refresh_drive_cache
from evidence.evidence_handler import update_file_name_with_timestamp
from evidence.models import Evidence, IgnoreWord
from laika.backends.concierge_backend import ConciergeAuthenticationBackend
from laika.backends.laika_backend import AuthenticationBackend
from laika.decorators import laika_service, service
from laika.utils.exceptions import GENERIC_FILES_ERROR_MSG, service_exception
from laika.utils.files import get_html_file_content
from laika.utils.get_organization_by_user_type import get_organization_by_user_type
from laika.utils.history import create_revision
from user.helpers import get_user_by_email

from .inputs import (
    AddDriveEvidenceInput,
    AddLaikaPaperIgnoreWordInput,
    CreateLaikaPaperInput,
    DeleteDriveEvidenceInput,
    UpdateDocumentInput,
    UpdateDocumentOwnerInput,
    UpdateLaikaPaperInput,
)

logger = logging.getLogger('drive_mutations')


class AddDriveEvidence(graphene.Mutation):
    class Arguments:
        input = AddDriveEvidenceInput(required=True)

    evidence_ids = graphene.List(graphene.Int)

    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'drive.add_driveevidence',
            },
        ],
        exception_msg=GENERIC_FILES_ERROR_MSG,
        revision_name='Files added to drive',
    )
    def mutate(self, info, input):
        organization = get_organization_by_user_type(
            info.context.user, input.organization_id
        )
        return AddDriveEvidence(
            upload_drive_file(
                organization,
                input.get('uploaded_files', []),
                info.context.user,
                input.get('is_onboarding'),
                input.get('description'),
            )
        )


class DeleteDriveEvidence(graphene.Mutation):
    class Arguments:
        input = DeleteDriveEvidenceInput(required=True)

    evidence_ids = graphene.List(graphene.Int)

    @transaction.atomic
    @service_exception('Failed to delete files')
    @create_revision('Files deleted from documents')
    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'drive.delete_driveevidence',
            },
        ],
        exception_msg='Failed to delete files',
    )
    def mutate(self, info, input):
        organization = get_organization_by_user_type(
            info.context.user, input.organization_id
        )

        drive = organization.drive
        refresh_drive_cache.delay(organization.id, input.evidence_ids, action='DELETE')

        filenames = list(
            drive.evidence.filter(evidence_id__in=input.evidence_ids).values_list(
                'evidence__name', flat=True
            )
        )

        drive.evidence.filter(evidence_id__in=input.evidence_ids).delete()
        delete_evidences_from_s3.delay(filenames)

        return DeleteDriveEvidence(input.evidence_ids)


class CreateLaikaPaper(graphene.Mutation):
    class Arguments:
        input = CreateLaikaPaperInput()

    laika_paper_id = graphene.Int()

    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.add_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'drive.add_driveevidence',
            },
        ],
        revision_name='Laika paper created in drive',
        exception_msg='Failed to create Laika Paper. Please try again.',
    )
    def mutate(self, info, input):
        organization = get_organization_by_user_type(
            info.context.user, input.organization_id
        )
        laika_paper = create_laika_paper_evidence(
            organization, info.context.user, input.get('template_id')
        )

        return CreateLaikaPaper(laika_paper_id=laika_paper.id)


class UpdateLaikaPaper(graphene.Mutation):
    class Arguments:
        input = UpdateLaikaPaperInput(required=True)

    laika_paper_id = graphene.Int()

    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.change_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'drive.change_driveevidence',
            },
        ],
        revision_name='Laika paper updated in drive',
        exception_msg='Failed to update Laika Paper. Please try again.',
    )
    def mutate(self, info, input):
        organization = get_organization_by_user_type(
            info.context.user, input.organization_id
        )
        laika_paper = Evidence.objects.get(
            organization=organization,
            id=input.laika_paper_id,
            type=constants.LAIKA_PAPER,
        )
        laika_paper.file = File(
            name=update_file_name_with_timestamp(laika_paper.name),
            file=io.BytesIO(input.laika_paper_content.encode()),
        )
        laika_paper.evidence_text = get_html_file_content(
            laika_paper.file, laika_paper.id
        )
        laika_paper.save()

        return UpdateLaikaPaper(laika_paper.id)


class AddLaikaPaperIgnoreWord(graphene.Mutation):
    class Arguments:
        input = AddLaikaPaperIgnoreWordInput(required=True)

    ignore_word_id = graphene.Int()

    @laika_service(
        permission='drive.add_driveevidence',
        exception_msg='Failed to add ignore word in Laika paper. Please try again.',
        revision_name='Added ignore word in Laika paper',
    )
    def mutate(self, info, input):
        ignore_word = IgnoreWord.objects.custom_create(
            organization=info.context.user.organization,
            laika_paper_id=input.laika_paper_id,
            evidence_type=constants.LAIKA_PAPER,
            laika_paper_language=input.laika_paper_language,
            laika_paper_ignore_word=input.laika_paper_ignore_word,
        )

        return AddLaikaPaperIgnoreWord(ignore_word.id)


class UpdateDocumentOwner(graphene.Mutation):
    class Arguments:
        input = UpdateDocumentOwnerInput(required=True)

    document_id = graphene.Int()

    @transaction.atomic
    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'drive.change_driveevidence',
            },
        ],
        exception_msg='Failed to change the owner. Please try again.',
    )
    def mutate(self, info, input):
        organization = get_organization_by_user_type(
            info.context.user, input.organization_id
        )
        drive = organization.drive
        drive_evidence = drive.evidence.get(evidence_id=input.evidence_id)
        drive_evidence.owner = get_user_by_email(
            organization_id=organization.id, email=input.owner_email
        )

        drive_evidence.save()
        return UpdateDocumentOwner(drive_evidence.evidence.id)


class UpdateDocument(graphene.Mutation):
    class Arguments:
        input = UpdateDocumentInput(required=True)

    updated = graphene.Int()

    @staticmethod
    @laika_service(
        permission='drive.change_driveevidence',
        exception_msg='Failed to update document. Please try again.',
        revision_name='Update document description',
    )
    def mutate(self, info, **kwargs):
        drive = info.context.user.organization.drive
        document_input = kwargs.get('input')
        drive_evidence = drive.evidence.get(evidence_id=document_input.evidence_id)
        drive_evidence.evidence.description = document_input.description
        drive_evidence.evidence.save()

        return UpdateDocument(drive_evidence.evidence.id)

import json
import logging

import graphene
import reversion
from django.db import transaction

from dataroom.evidence_handler import delete_evidence
from dataroom.inputs import (
    AddDataroomDocumentsInput,
    CreateDataroomInput,
    DeleteDataroomDocumentsInput,
    ToggleDataroomInput,
)
from dataroom.models import Dataroom
from dataroom.services.dataroom import DataroomService
from dataroom.types import DataroomType
from laika.auth import login_required, permission_required
from laika.backends.concierge_backend import ConciergeAuthenticationBackend
from laika.backends.laika_backend import AuthenticationBackend
from laika.decorators import service
from laika.utils.exceptions import GENERIC_FILES_ERROR_MSG, service_exception
from laika.utils.get_organization_by_user_type import get_organization_by_user_type
from laika.utils.history import create_revision

logger = logging.getLogger('dataroom_mutations')


class CreateDataroom(graphene.Mutation):
    class Arguments:
        input = CreateDataroomInput(required=True)

    data = graphene.Field(DataroomType)

    @login_required
    @transaction.atomic
    @service_exception('Failed to create dataroom')
    @permission_required('dataroom.add_dataroom')
    @create_revision('Created dataroom')
    def mutate(self, info, input):
        name = input.get('name')
        user = info.context.user
        organization = user.organization

        dataroom = DataroomService.create_dataroom(name=name, organization=organization)
        return CreateDataroom(data=dataroom)


class ToggleDataroom(graphene.Mutation):
    class Arguments:
        input = ToggleDataroomInput(required=True)

    id = graphene.Int()

    @login_required
    @transaction.atomic
    @service_exception('Failed to delete dataroom')
    @permission_required('dataroom.delete_dataroom')
    def mutate(self, info, input):
        id = input.get('id')
        is_soft_deleted = input.get('is_soft_deleted')
        organization_id = info.context.user.organization_id

        with reversion.create_revision():
            reversion.set_user(info.context.user)
            datarooms_to_toggle = Dataroom.objects.filter(
                organization_id=organization_id, id=id
            )

            if is_soft_deleted:
                reversion.set_comment(
                    f'Deleted datarooms {[dr.name for dr in datarooms_to_toggle]}'
                )
            else:
                reversion.set_comment(
                    f'Restored datarooms {[dr.name for dr in datarooms_to_toggle]}'
                )

            for dr in datarooms_to_toggle:
                dr.is_soft_deleted = is_soft_deleted
                dr.save()

            return ToggleDataroom(id=id)


class AddDataroomDocuments(graphene.Mutation):
    class Arguments:
        input = AddDataroomDocumentsInput(required=True)

    document_ids = graphene.List(graphene.String)

    @transaction.atomic
    @service_exception(GENERIC_FILES_ERROR_MSG)
    @create_revision('Documents added to dataroom')
    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'dataroom.add_dataroomevidence',
            },
        ],
        exception_msg='Failed to add documents to dataroom',
    )
    def mutate(self, info, input):
        organization = get_organization_by_user_type(
            info.context.user, input.organization_id
        )
        dataroom = Dataroom.objects.get(organization=organization, id=input.id)

        uploaded_files = input.get('uploaded_files', [])
        documents = input.get('documents', [])
        other_evidence = input.get('other_evidence', [])
        officers = input.get('officers', [])
        teams = input.get('teams', [])
        policies = input.get('policies', [])
        time_zone = input.time_zone

        document_ids = DataroomService.add_documents_to_dataroom(
            organization=organization,
            dataroom=dataroom,
            uploaded_files=uploaded_files,
            documents=documents,
            other_evidence=other_evidence,
            officers=officers,
            teams=teams,
            policies=policies,
            time_zone=time_zone,
        )

        return AddDataroomDocuments(document_ids=document_ids)


class DeleteDataroomDocuments(graphene.Mutation):
    class Arguments:
        input = DeleteDataroomDocumentsInput(required=True)

    success = graphene.Boolean(default_value=True)

    @login_required
    @transaction.atomic
    @service_exception('Failed to delete documents from dataroom')
    @permission_required('dataroom.delete_dataroomevidence')
    def mutate(self, info, input):
        organization = info.context.user.organization
        dataroom = Dataroom.objects.get(id=input.id, organization=organization)
        with reversion.create_revision():
            reversion.set_comment('Delete dataroom documents')
            reversion.set_user(info.context.user)

            documents_to_delete = input.get('documents', [])
            documents = json.loads(documents_to_delete[0])
            doc_ids = [doc['id'] for doc in documents]

            delete_evidence(organization, doc_ids, dataroom)
            dataroom.save()  # update last updated date to today.
            logger.info(
                f'Dataroom evidence ids {doc_ids} in '
                f'organization {organization} and '
                f'dataroom {dataroom} deleted'
            )
            return DeleteDataroomDocuments()

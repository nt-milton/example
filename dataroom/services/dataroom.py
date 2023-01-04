import logging

from dataroom.evidence_handler import (
    add_dataroom_documents,
    add_dataroom_other_evidence,
    add_dataroom_policy,
    add_dataroom_teams,
    add_officers_report_to_dataroom,
    upload_dataroom_file,
)
from dataroom.models import Dataroom
from laika.utils.exceptions import ServiceException
from organization.models import Organization

logger = logging.getLogger(__name__)


class DataroomService:
    @staticmethod
    def add_documents_to_dataroom(
        *,
        organization: Organization,
        dataroom: Dataroom,
        uploaded_files=[],
        documents=[],
        other_evidence=[],
        officers=[],
        teams=[],
        policies=[],
        time_zone,
    ):
        if dataroom.is_soft_deleted:
            dataroom.is_soft_deleted = False

        added_files_ids = upload_dataroom_file(organization, uploaded_files, dataroom)

        added_documents_ids = add_dataroom_documents(
            organization, documents, dataroom, time_zone
        )

        added_other_evidence_ids = add_dataroom_other_evidence(
            organization, other_evidence, dataroom
        )
        added_officer_ids = add_officers_report_to_dataroom(
            organization, officers, dataroom, time_zone
        )
        added_teams_ids = add_dataroom_teams(organization, teams, dataroom, time_zone)
        added_policies_ids = add_dataroom_policy(
            organization, policies, dataroom, time_zone
        )

        document_ids = (
            added_files_ids
            + added_documents_ids
            + added_other_evidence_ids
            + added_officer_ids
            + added_teams_ids
            + added_policies_ids
        )

        dataroom.save()

        return document_ids

    @staticmethod
    def create_dataroom(*, name: str, organization: Organization):
        dataroom_exist = Dataroom.objects.filter(
            name=name, organization=organization
        ).exists()

        if dataroom_exist:
            logger.info(
                f'Dataroom with name {name} already '
                f'exists in organization id {organization.id}'
            )
            raise ServiceException('A record with the given name already exists.')

        dataroom = Dataroom.objects.create(organization=organization, name=name)

        return dataroom

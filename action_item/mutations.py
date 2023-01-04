import json
import logging

import graphene

import evidence.constants as constants
from action_item.inputs import ActionItemEvidenceInput, DeleteActionItemEvidenceInput
from action_item.models import ActionItem
from action_item.types import ActionItemEvidenceType
from evidence.models import Evidence
from laika.decorators import laika_service

from .evidence_handler import (
    add_action_item_documents_or_laika_papers,
    add_action_item_officers,
    add_action_item_other_evidence,
    add_action_item_policy,
    add_action_item_teams,
    add_note_to_action_item,
    delete_evidence,
    upload_action_item_file,
)

logger = logging.getLogger('__name__')


class AddActionItemEvidence(graphene.Mutation):
    class Arguments:
        input = ActionItemEvidenceInput(required=True)

    evidences = graphene.List(ActionItemEvidenceType)

    @laika_service(
        permission='action_item.change_actionitem',
        exception_msg='Failed to add evidence to action item.',
    )
    def mutate(self, info, input):
        organization = info.context.user.organization
        action_item = ActionItem.objects.get(pk=input.id)
        added_files_ids = upload_action_item_file(
            organization, input.get('files', []), action_item
        )
        added_policies_ids = add_action_item_policy(
            organization, input.get('policies', []), action_item, input.time_zone
        )
        added_laika_papers_ids = add_action_item_documents_or_laika_papers(
            organization,
            input.get('documents', []),
            action_item,
            file_type=constants.LAIKA_PAPER,
        )
        added_documents_ids = add_action_item_documents_or_laika_papers(
            organization,
            input.get('documents', []),
            action_item,
            file_type=constants.FILE,
        )
        added_other_evidence_ids = add_action_item_other_evidence(
            organization, input.get('other_evidence', []), action_item
        )
        added_teams_ids = add_action_item_teams(
            organization, input.get('teams', []), action_item, input.time_zone
        )
        added_officer_ids = add_action_item_officers(
            organization, input.get('officers', []), action_item, input.time_zone
        )
        added_note_ids = add_note_to_action_item(
            organization,
            info.context.user,
            input.get('laika_paper', dict()),
            action_item,
        )
        evidence_ids = (
            added_files_ids
            + added_policies_ids
            + added_documents_ids
            + added_other_evidence_ids
            + added_teams_ids
            + added_officer_ids
            + added_laika_papers_ids
            + added_note_ids
        )
        action_item.evidences.add(evidence_ids[0])
        return AddActionItemEvidence(
            evidences=Evidence.objects.filter(id__in=evidence_ids)
        )


class DeleteActionItemEvidence(graphene.Mutation):
    class Arguments:
        input = DeleteActionItemEvidenceInput(required=True)

    evidences = graphene.List(ActionItemEvidenceType)

    @laika_service(
        permission='action_item.change_actionitem',
        exception_msg='Failed to delete evidence from action item.',
    )
    def mutate(self, info, input):
        action_item = ActionItem.objects.get(pk=input.id)
        evidence_to_delete = []
        all_evidence = json.loads(input.evidence[0])

        for evidence in all_evidence:
            evidence_to_delete.append(evidence['id'])

        delete_evidence(
            evidence_to_delete, action_item, info.context.user.organization.id
        )

        logger.info(f'Action item evidence ids {evidence_to_delete} deleted')
        return DeleteActionItemEvidence(
            evidences=Evidence.objects.filter(id__in=evidence_to_delete)
        )

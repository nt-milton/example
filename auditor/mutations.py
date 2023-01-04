import logging

import graphene

from audit.models import Audit
from fieldwork.constants import ER_STATUS_DICT
from fieldwork.inputs import (
    AddEvidenceAttachmentInput,
    AssignEvidenceInput,
    DeleteAllEvidenceAttachmentInput,
    DeleteAuditorEvidenceAttachmentInput,
    RenameAttachmentInput,
    UpdateAuditorCriteriaInput,
    UpdateEvidenceInput,
    UpdateEvidenceStatusInput,
)
from fieldwork.models import (
    Attachment,
    Criteria,
    Evidence,
    EvidenceStatusTransition,
    Requirement,
    RequirementEvidence,
)
from fieldwork.types import CriteriaType, FieldworkEvidenceType
from fieldwork.util.evidence_attachment import delete_all_evidence_attachments
from fieldwork.util.evidence_request import calculate_er_times_move_back_to_open
from fieldwork.utils import (
    add_attachment,
    assign_evidence_user,
    bulk_laika_review_evidence,
    update_evidence_status,
)
from laika.decorators import audit_service
from laika.utils.exceptions import GENERIC_FILES_ERROR_MSG, ServiceException
from user.models import User

from .inputs import (
    AddAuditorEvidenceRequestInput,
    DeleteAuditEvidenceInput,
    UpdateAuditorEvidenceRequestInput,
)
from .utils import increment_display_id, is_auditor_associated_to_audit_firm

logger = logging.getLogger('auditor_mutation')


class AssignAuditorEvidence(graphene.Mutation):
    class Arguments:
        input = AssignEvidenceInput(required=True)

    assigned = graphene.List(graphene.String)

    @audit_service(
        permission='fieldwork.assign_evidence',
        exception_msg='Failed to assign evidence.',
        revision_name='Update evidence assignee',
    )
    def mutate(self, info, input):
        assigned = assign_evidence_user(input)
        return AssignAuditorEvidence(assigned=assigned)


class DeleteAuditEvidence(graphene.Mutation):
    class Arguments:
        input = DeleteAuditEvidenceInput(required=True)

    deleted = graphene.List(graphene.String)

    @audit_service(
        permission='fieldwork.delete_evidence',
        exception_msg='Failed to delete evidence',
        revision_name='Delete evidence',
    )
    def mutate(self, info, input):
        audit_evidence_ids = input.get('evidence_ids')
        audit_id = input.get('audit_id')

        audit_evidence_list = Evidence.objects.filter(
            id__in=audit_evidence_ids, audit_id=audit_id
        )

        if not audit_evidence_list.exists():
            logger.info(f'Evidence not found for audit: {audit_id}')

        new_evidence = []
        for evidence in audit_evidence_list:
            evidence.is_deleted = True
            new_evidence.append(evidence)

        Evidence.objects.bulk_update(new_evidence, ['is_deleted'])
        RequirementEvidence.objects.filter(evidence_id__in=audit_evidence_ids).delete()
        return DeleteAuditEvidence(deleted=audit_evidence_ids)


class AddAuditorEvidenceAttachment(graphene.Mutation):
    class Arguments:
        input = AddEvidenceAttachmentInput(required=True)

    document_ids = graphene.List(graphene.Int)

    @audit_service(
        permission='fieldwork.add_evidence_attachment',
        exception_msg=GENERIC_FILES_ERROR_MSG,
        revision_name='Add attachment to evidence',
        atomic=True,
    )
    def mutate(self, info, input):
        fieldwork_evidence = Evidence.objects.get(id=input.id)
        if not is_auditor_associated_to_audit_firm(
            fieldwork_evidence.audit, info.context.user.id
        ):
            raise ServiceException('Auditor can not add attachments')
        ids = add_attachment(fieldwork_evidence=fieldwork_evidence, input=input)
        return AddAuditorEvidenceAttachment(ids)


class UpdateAuditorEvidenceStatus(graphene.Mutation):
    class Arguments:
        input = UpdateEvidenceStatusInput(required=True)

    updated = graphene.List(graphene.String)

    @audit_service(
        permission='fieldwork.change_evidence',
        exception_msg='Failed to change evidence status',
        revision_name='Change evidence status',
    )
    def mutate(self, info, input):
        evidence = Evidence.objects.filter(
            id__in=input.get('ids'), audit_id=input.get('audit_id')
        )
        updated_evidence = update_evidence_status(
            evidence,
            input.get('status'),
            transitioned_by=info.context.user,
            transition_reasons=input.get('transition_reasons', ''),
            extra_notes=input.get('extra_notes'),
        )

        Evidence.objects.bulk_update(
            updated_evidence, ['status', 'times_moved_back_to_open']
        )

        # TODO: Refactor on FZ-2548
        if input.get('status') == 'open':
            updated_evidence = bulk_laika_review_evidence(evidence, back_to_open=True)
            Evidence.objects.bulk_update(
                updated_evidence,
                ['is_laika_reviewed'],
            )
        return UpdateAuditorEvidenceStatus(updated=input.get('ids'))


class UpdateAuditorEvidence(graphene.Mutation):
    class Arguments:
        input = UpdateEvidenceInput(required=True)

    evidence_updated = graphene.String()

    @audit_service(
        permission='fieldwork.change_evidence',
        exception_msg='Failed to update evidence',
        revision_name='Update customer evidence',
    )
    def mutate(self, info, input):
        evidence_id = input.get('evidence_id')
        auditor_evidence = Evidence.objects.get(
            id=evidence_id, audit__id=input.get('audit_id')
        )
        current_laika_review_value = auditor_evidence.is_laika_reviewed
        new_status = input.get('status')

        if new_status == 'open':
            auditor_evidence.is_laika_reviewed = False
            auditor_evidence.times_moved_back_to_open = (
                calculate_er_times_move_back_to_open(auditor_evidence)
            )

        assignee_email = input.get('assignee_email')

        if not assignee_email:
            assignee = None
        else:
            assignee = User.objects.get(email=assignee_email)

        if 'assignee_email' in input:
            auditor_evidence.assignee = assignee

        if new_status:
            from_status = auditor_evidence.status

            EvidenceStatusTransition.objects.create(
                evidence=auditor_evidence,
                from_status=from_status,
                to_status=new_status,
                transition_reasons=input.get('transition_reasons', ''),
                extra_notes=input.get('extra_notes'),
                laika_reviewed=current_laika_review_value,
                transitioned_by=info.context.user,
            )

        updated_evidence = input.to_model(update=auditor_evidence)

        return UpdateAuditorEvidence(evidence_updated=updated_evidence.id)


class RenameAuditorEvidenceAttachment(graphene.Mutation):
    class Arguments:
        input = RenameAttachmentInput(required=True)

    updated = graphene.String()

    @audit_service(
        permission='fieldwork.change_evidence',
        exception_msg='Failed to rename evidence attachment',
        revision_name='Rename auditor evidence attachment',
    )
    def mutate(self, info, input):
        attachment_id = input.attachment_id
        evidence_id = input.evidence_id
        user_id = info.context.user.id

        evidence = Evidence.objects.get(id=evidence_id)

        if not is_auditor_associated_to_audit_firm(evidence.audit, user_id):
            raise ServiceException("Auditor can not rename attachments")

        attachment = Attachment.objects.get(
            id=attachment_id,
            evidence_id=evidence_id,
        )
        attachment.rename(input)

        return RenameAuditorEvidenceAttachment(updated=attachment.id)


class DeleteAuditorEvidenceAttachment(graphene.Mutation):
    class Arguments:
        input = DeleteAuditorEvidenceAttachmentInput(required=True)

    attachment_id = graphene.String()
    evidence_id = graphene.String()

    @audit_service(
        permission='fieldwork.delete_evidence_attachment',
        exception_msg='Failed to delete evidence attachment',
        revision_name='Delete evidence attachment',
        atomic=True,
    )
    def mutate(self, info, input):
        attachment_id = input.attachment_id
        user_id = info.context.user.id
        evidence_id = input.evidence_id
        audit_id = input.audit_id

        evidence = Evidence.objects.get(id=evidence_id, audit__id=audit_id)

        if not is_auditor_associated_to_audit_firm(evidence.audit, user_id):
            raise ServiceException("Auditor can not delete attachments")
        Attachment.objects.filter(pk=attachment_id, evidence__id=evidence_id).update(
            is_deleted=True, deleted_by=info.context.user
        )
        return DeleteAuditorEvidenceAttachment(
            attachment_id=attachment_id, evidence_id=evidence_id
        )


class AddAuditorEvidenceRequest(graphene.Mutation):
    class Arguments:
        input = AddAuditorEvidenceRequestInput(required=True)

    evidence = graphene.Field(FieldworkEvidenceType)

    @audit_service(
        permission='fieldwork.add_evidence',
        exception_msg='Failed to add audit evidence.',
        revision_name='Add audit evidence',
    )
    def mutate(self, info, input):
        user = info.context.user

        audit_id = input.get('audit_id')

        audit = Audit.objects.get(id=audit_id)

        logger.info(
            f'Auditor user: {user.username} is creating an evidence in audit {audit.id}'
        )

        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
            raise ServiceException("Auditor can not create evidence")

        new_display_id = increment_display_id(Evidence, audit_id, 'ER')

        related_requirements_ids = input.get('related_requirements_ids')
        evidence = Evidence.objects.create(
            display_id=new_display_id,
            audit=audit,
            name=input.get('name'),
            instructions=input.get('instructions'),
        )

        requirements = Requirement.objects.filter(id__in=related_requirements_ids)
        for requirement in requirements:
            RequirementEvidence.objects.create(
                evidence=evidence, requirement=requirement
            )

        return AddAuditorEvidenceRequest(evidence=evidence)


class UpdateAuditorEvidenceRequest(graphene.Mutation):
    class Arguments:
        input = UpdateAuditorEvidenceRequestInput(required=True)

    evidence = graphene.Field(FieldworkEvidenceType)

    @audit_service(
        permission='fieldwork.change_evidence',
        exception_msg='Failed to update audit evidence.',
        revision_name='Update audit evidence',
    )
    def mutate(self, info, input):
        user = info.context.user

        audit_id = input.get('audit_id')
        evidence_id = input.get('evidence_id')
        new_name = input.get('name')
        new_instructions = input.get('instructions')
        related_requirements_ids = input.get('related_requirements_ids')

        audit = Audit.objects.get(id=audit_id)

        logger.info(
            f'Auditor user: {user.username} is updating'
            f'the evidence {evidence_id} in audit {audit.id}'
        )

        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
            raise ServiceException("Auditor can not update evidence")

        if (
            len(related_requirements_ids) <= 0
            or new_name == ''
            or new_instructions == ''
        ):
            raise ServiceException('Required field not provided to update an evidence')

        evidence = Evidence.objects.get(id=evidence_id, audit_id=audit_id)

        if evidence.status != ER_STATUS_DICT['Open']:
            raise ServiceException('Status of the evidence should be open for updating')

        evidence.name = new_name
        evidence.instructions = new_instructions
        evidence.save()

        RequirementEvidence.objects.filter(evidence=evidence).delete()

        requirements = Requirement.objects.filter(id__in=related_requirements_ids)
        for requirement in requirements:
            RequirementEvidence.objects.create(
                evidence=evidence, requirement=requirement
            )

        return UpdateAuditorEvidenceRequest(evidence=evidence)


class DeleteAuditorAllEvidenceAttachments(graphene.Mutation):
    class Arguments:
        input = DeleteAllEvidenceAttachmentInput(required=True)

    evidence = graphene.List(FieldworkEvidenceType)

    @audit_service(
        permission='fieldwork.delete_evidence_attachment',
        exception_msg='Failed to delete evidence attachments',
        revision_name='Delete all evidence attachments',
    )
    def mutate(self, info, input):
        evidence = delete_all_evidence_attachments(
            input.audit_id, input.evidence_ids, info.context.user
        )
        return DeleteAuditorAllEvidenceAttachments(evidence=evidence)


class UpdateAuditorCriteria(graphene.Mutation):
    class Arguments:
        input = UpdateAuditorCriteriaInput(required=True)

    criteria = graphene.Field(CriteriaType)

    @audit_service(
        permission='fieldwork.change_criteria',
        exception_msg='Failed to update criteria.',
        revision_name='Update criteria',
    )
    def mutate(self, info, input):
        audit_id = input.get('audit_id')
        criteria_id = input.get('criteria_id')
        user = info.context.user
        audit = Audit.objects.get(id=audit_id)
        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
            raise ServiceException("Auditor can not update criteria")

        criteria = Criteria.objects.get(id=criteria_id, audit_id=audit_id)

        update_fields = []
        for input_field in input.fields:
            field = input_field.field
            value = (
                input_field.value if input_field.value else input_field.boolean_value
            )
            update_fields.append(field)
            setattr(criteria, field, value)
        criteria.save(update_fields=update_fields)
        return UpdateAuditorCriteria(criteria=criteria)

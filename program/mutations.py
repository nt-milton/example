import logging

import graphene
import reversion
from django.db import transaction

from alert.constants import ALERT_TYPES
from drive.models import DriveEvidence, DriveEvidenceData
from drive.tasks import refresh_drive_cache
from evidence.constants import FILE
from evidence.evidence_handler import get_files_to_upload
from evidence.models import Evidence, SystemTagEvidence, TagEvidence
from laika.auth import login_required, permission_required
from laika.utils.dates import str_date_to_date_formatted
from laika.utils.exceptions import (
    GENERIC_FILES_ERROR_MSG,
    ServiceException,
    service_exception,
)
from laika.utils.history import create_revision
from program.constants import MAPPED_TASKS_TIERS, SUBTASK_COMPLETED_STATUS
from program.inputs import (
    AddSubTaskEvidenceInput,
    CreateSubTaskInput,
    CreateTaskInput,
    DeleteSubTaskEvidenceInput,
    UpdateProgramInput,
    UpdateSubTaskAssigneeInput,
    UpdateSubTaskDueDateInput,
    UpdateSubTaskInput,
    UpdateSubTaskStatusInput,
    UpdateTaskInput,
)
from program.models import Program, SubTask, Task
from program.types import ProgramType, SubTaskType, TaskType
from tag.models import Tag
from user.helpers import get_user_by_email
from user.inputs import DeleteInput

logger = logging.getLogger('program_mutations')


def strip_comment_reply_content(content):
    return content.strip() if content else None


def has_new_assignee(input_assignee_email, current_assignee):
    if not input_assignee_email:
        return False
    if not current_assignee:
        return True
    return current_assignee != input_assignee_email


def validate_comment_content(content, user_email):
    if not content:
        logger.error(f'Trying to create a comment with empty contentuser {user_email}')
        raise ServiceException('Comment content cannot be empty')


class CreateTask(graphene.Mutation):
    class Arguments:
        input = CreateTaskInput(required=True)

    task = graphene.Field(TaskType)

    @login_required
    @transaction.atomic
    @service_exception('Cannot create task')
    @permission_required('program.add_task')
    @create_revision('Created task')
    def mutate(self, info, input):
        organization_id = info.context.user.organization_id
        program = Program.objects.get(
            organization_id=organization_id, id=input.program_id
        )
        task_exists = Task.objects.filter(
            name=input.get('name'), program=program
        ).exists()

        if task_exists:
            raise ServiceException('Task with that name already exists')

        task = input.to_model(
            program=program,
            name=input.get('name'),
            category=input.get('category'),
            tier=input.get('tier'),
            overview=input.get('overview'),
        )

        return CreateTask(task=task)


class UpdateTask(graphene.Mutation):
    class Arguments:
        input = UpdateTaskInput(required=True)

    task = graphene.Field(TaskType)

    @login_required
    @transaction.atomic
    @service_exception('Failed to update task. Please try again.')
    @permission_required('program.change_task')
    @create_revision('Updated task')
    def mutate(self, info, input):
        organization = info.context.user.organization
        current_task = Task.objects.get(id=input.id, program__organization=organization)

        task = input.to_model(
            update=current_task,
            # This is because trying to save it with the
            # new mapped tier didn't store it correctly
            save=False,
        )
        if input.tier:
            task.tier = MAPPED_TASKS_TIERS[input.tier]
        task.save()

        return UpdateTask(task=task)


class UpdateTaskNotes(graphene.Mutation):
    class Arguments:
        input = UpdateTaskInput(required=True)

    task = graphene.Field(TaskType)

    @login_required
    @transaction.atomic
    @service_exception('Failed to update task notes. Please try again.')
    @permission_required('program.change_task_implementation_notes')
    @create_revision('Updated task notes')
    def mutate(self, info, input):
        organization = info.context.user.organization
        current_task = Task.objects.get(id=input.id, program__organization=organization)

        task = input.to_model(update=current_task)

        return UpdateTask(task=task)


class CreateSubTask(graphene.Mutation):
    class Arguments:
        input = CreateSubTaskInput(required=True)

    subtask = graphene.Field(SubTaskType)

    @login_required
    @transaction.atomic
    @service_exception('Cannot create subtask')
    @permission_required('program.add_subtask')
    @create_revision('Created subtask')
    def mutate(self, info, input):
        organization = info.context.user.organization
        assignee_email = input.get('assignee_email')
        task = Task.objects.get(program__organization=organization, id=input.task_id)
        subtask_exists = SubTask.objects.filter(
            task=task, text=input.get('text')
        ).exists()

        if subtask_exists:
            raise ServiceException('SubTask with that name already exists')

        owner = None
        if assignee_email:
            owner = get_user_by_email(
                organization_id=organization.id, email=input.get('assignee_email')
            )
        subtask = input.to_model(
            task=task, assignee=owner, is_system_subtask=False, save=False
        )
        # Get the right sort index
        subtask.save()

        if assignee_email:
            subtask.create_subtask_alert(
                alert_type=ALERT_TYPES['NEW_ASSIGNMENT'], sender=info.context.user
            )
        return CreateSubTask(subtask=subtask)


class UpdateSubTask(graphene.Mutation):
    class Arguments:
        input = UpdateSubTaskInput(required=True)

    subtask = graphene.Field(SubTaskType)

    @login_required
    @transaction.atomic
    @service_exception('Cannot update subtask')
    @permission_required('program.change_subtask')
    @create_revision('Updated subtask')
    def mutate(self, info, input):
        organization = info.context.user.organization
        input_assignee_email = input.get('assignee_email')
        current_subtask = SubTask.objects.get(
            task__program__organization=organization,
            id=input.get('id'),
        )
        current_subtask.assignee = get_user_by_email(
            organization_id=organization.id, email=input.get('assignee_email')
        )

        if 'due_date' in input:
            current_subtask.due_date = input.get('due_date') or None

        subtask = input.to_model(update=current_subtask)

        if has_new_assignee(
            input_assignee_email=input_assignee_email,
            current_assignee=current_subtask.assignee,
        ):
            # create the assigned alert
            sender = info.context.user

            subtask.create_subtask_alert(
                alert_type=ALERT_TYPES['NEW_ASSIGNMENT'], sender=sender
            )
        return UpdateSubTask(subtask=subtask)


class UpdateSubTaskStatus(graphene.Mutation):
    class Arguments:
        input = UpdateSubTaskStatusInput(required=True)

    subtask = graphene.Field(SubTaskType)

    @login_required
    @transaction.atomic
    @service_exception('Cannot update subtask status')
    @permission_required('program.change_subtask_partial')
    @create_revision('Updated subtask status')
    def mutate(self, info, input):
        organization = info.context.user.organization
        if not input.get('status'):
            raise ServiceException('Missing status for subtask.')

        current_subtask = SubTask.objects.get(
            task__program__organization=organization,
            id=input.get('id'),
        )

        subtask_is_completed = input.get('status') == SUBTASK_COMPLETED_STATUS

        current_subtask.completed_on = (
            str_date_to_date_formatted(input.get('completed_at'))
            if subtask_is_completed
            else None
        )

        subtask = input.to_model(update=current_subtask)

        if subtask_is_completed and current_subtask.assignee:
            sender = info.context.user
            subtask.create_subtask_alert(
                alert_type=ALERT_TYPES['ASSIGNMENT_COMPLETED'], sender=sender
            )
        return UpdateSubTaskStatus(subtask=subtask)


class UpdateSubTaskDueDate(graphene.Mutation):
    class Arguments:
        input = UpdateSubTaskDueDateInput(required=True)

    subtask = graphene.Field(SubTaskType)

    @login_required
    @transaction.atomic
    @service_exception('Cannot update subtask due date')
    @permission_required('program.change_subtask_partial')
    @create_revision('Updated subtask due date')
    def mutate(self, info, input):
        organization = info.context.user.organization

        current_subtask = SubTask.objects.get(
            task__program__organization=organization,
            id=input.get('id'),
        )

        if 'due_date' in input:
            current_subtask.due_date = input.get('due_date') or None

        subtask = input.to_model(update=current_subtask)
        return UpdateSubTaskDueDate(subtask=subtask)


class UpdateSubTaskAssignee(graphene.Mutation):
    class Arguments:
        input = UpdateSubTaskAssigneeInput(required=True)

    subtask = graphene.Field(SubTaskType)

    @login_required
    @transaction.atomic
    @service_exception('Cannot update subtask assignee')
    @permission_required('program.change_subtask_partial')
    @create_revision('Updated subtask assignee')
    def mutate(self, info, input):
        organization = info.context.user.organization
        assignee_email = input.get('assignee_email')
        current_subtask = SubTask.objects.get(
            task__program__organization=organization,
            id=input.get('id'),
        )
        # Email can be set to unassigned
        current_subtask.assignee = get_user_by_email(
            organization_id=organization.id, email=assignee_email
        )
        subtask = input.to_model(update=current_subtask)

        sender = info.context.user

        if assignee_email:
            subtask.create_subtask_alert(
                alert_type=ALERT_TYPES['NEW_ASSIGNMENT'], sender=sender
            )

        return UpdateSubTaskAssignee(subtask=subtask)


class DeleteSubTask(graphene.Mutation):
    class Arguments:
        input = DeleteInput(required=True)

    id = graphene.String()

    @login_required
    @transaction.atomic
    @service_exception('Cannot delete subtask')
    @permission_required('program.delete_subtask')
    def mutate(self, info, input):
        organization = info.context.user.organization
        subtask = SubTask.objects.get(
            task__program__organization=organization, id=input.get('id')
        )
        with reversion.create_revision():
            reversion.set_comment('Deleted subtask')
            reversion.set_user(info.context.user)

            # Removes the Document’s tags linking it to that specific subtask
            SystemTagEvidence.objects.filter(
                evidence__in=subtask.evidence.values_list('id', flat=True),
                tag__name=str(subtask.id),
            ).delete()

            # Removes the Tag with name subtask id
            Tag.objects.filter(organization=organization, name=str(subtask.id)).delete()

            subtask_id = subtask.id
            subtask.delete()

            return DeleteSubTask(id=subtask_id)


class AddSubTaskEvidence(graphene.Mutation):
    class Arguments:
        input = AddSubTaskEvidenceInput(required=True)

    document_ids = graphene.List(graphene.Int)

    @login_required
    @transaction.atomic
    @service_exception(GENERIC_FILES_ERROR_MSG)
    @permission_required('program.add_subtaskevidence')
    @create_revision('Evidence added to subtask')
    def mutate(self, info, input):
        ids = []
        organization = info.context.user.organization
        subtask = SubTask.objects.get(
            task__program__organization=organization, pk=input.id
        )

        all_tags = subtask.get_tags_for_evidence(organization=organization)

        system_tags = all_tags.get('system_tags', [])

        system_tag = system_tags[0] if len(system_tags) else None

        uploaded_files = get_files_to_upload(input.get('uploaded_files', []))
        for file in uploaded_files:
            drive_evidence_data = DriveEvidenceData(type=FILE, file=file, **all_tags)
            drive_evidence = DriveEvidence.objects.custom_create(
                organization=organization,
                owner=info.context.user,
                drive_evidence_data=drive_evidence_data,
            )

            ids.append(drive_evidence.evidence.id)

        for document in input.get('documents', []):
            evidence = Evidence.objects.link_document(
                organization, document, system_tag
            )
            refresh_drive_cache.delay(organization.id, [evidence.id])
            ids.append(evidence.id)

        for policy in input.get('policies', []):
            evidence = Evidence.objects.create_policy(organization, policy)
            Evidence.objects.link_system_evidence(evidence, system_tag)
            ids.append(evidence.id)

        if input.get('teams', []):
            evidence_ids = DriveEvidence.objects.custom_create_teams(
                organization,
                input.time_zone,
                all_tags,
                input.get('teams'),
                info.context.user,
            )
            ids += evidence_ids

        if input.get('officers', []):
            evidence_ids = DriveEvidence.objects.custom_create_officers(
                organization,
                input.time_zone,
                all_tags,
                input.get('officers'),
                info.context.user,
            )
            ids += evidence_ids

        for evidence in Evidence.objects.filter(id__in=ids):
            for t in all_tags.get('tags'):
                evidence.tags.add(t)

        return AddSubTaskEvidence(document_ids=ids)


class DeleteSubTaskEvidence(graphene.Mutation):
    class Arguments:
        input = DeleteSubTaskEvidenceInput(required=True)

    evidence_id = graphene.String()

    @login_required
    @transaction.atomic
    @service_exception('Failed to delete evidence from subtask')
    @permission_required('program.delete_subtaskevidence')
    def mutate(self, info, input):
        organization = info.context.user.organization
        subtask = SubTask.objects.get(
            task__program__organization=organization, pk=input.id
        )
        with reversion.create_revision():
            reversion.set_comment('Deleted subtask evidence')
            reversion.set_user(info.context.user)
            evidence_id = input.get('evidence_id')

            evidence = Evidence.objects.get(organization=organization, id=evidence_id)
            if SystemTagEvidence.objects.filter(
                evidence=evidence, tag__name=str(subtask.id)
            ).exists():
                # Removes the Document’s tags linking it to that specific
                # subtask
                SystemTagEvidence.objects.filter(
                    evidence=evidence, tag__name=str(subtask.id)
                ).delete()

                refresh_drive_cache.delay(organization.id, [evidence.id])

            if TagEvidence.objects.filter(
                evidence=evidence, tag__name=str(subtask.task.category)
            ).exists():
                TagEvidence.objects.filter(
                    evidence=evidence, tag__name=str(subtask.task.category)
                ).delete()

                refresh_drive_cache.delay(organization.id, [evidence.id])

            logger.info(
                f'Subtask evidence id {evidence_id} in '
                f'organization {organization} deleted'
            )
            return DeleteSubTaskEvidence(evidence_id=evidence_id)


class UpdateProgram(graphene.Mutation):
    class Arguments:
        input = UpdateProgramInput(required=True)

    program = graphene.Field(ProgramType)

    @login_required
    @transaction.atomic
    @service_exception('Failed to update program. Please try again.')
    @permission_required('program.change_program')
    @create_revision('Updated program')
    def mutate(self, info, input):
        organization = info.context.user.organization
        email = input.get('program_lead_email')
        current_program = Program.objects.get(id=input.id, organization=organization)

        current_program.program_lead = get_user_by_email(
            organization_id=organization.id, email=email
        )

        email = input.get('program_lead_email')
        if email:
            current_program.program_lead = get_user_by_email(
                organization_id=organization.id, email=email
            )

        program = input.to_model(update=current_program)

        return UpdateProgram(program=program)

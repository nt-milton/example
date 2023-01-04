import graphene

from certification.models import CertificationSection
from control.models import Control
from control.types import ControlType
from control.utils.status import get_progress
from laika.auth import login_required, permission_required
from laika.aws.dynamo import get_policies, get_programs, get_tasks_by_program
from laika.decorators import concierge_service
from laika.utils.exceptions import service_exception
from program.constants import FINISH_LINE_TIER, GETTING_STARTED_TIER, NEXT_STEPS_TIER
from program.models import (
    ArchivedEvidence,
    ArchivedProgram,
    ArchivedTask,
    Program,
    SubTask,
    Task,
)
from program.mutations import (
    AddSubTaskEvidence,
    CreateSubTask,
    CreateTask,
    DeleteSubTask,
    DeleteSubTaskEvidence,
    UpdateProgram,
    UpdateSubTask,
    UpdateSubTaskAssignee,
    UpdateSubTaskDueDate,
    UpdateSubTaskStatus,
    UpdateTask,
    UpdateTaskNotes,
)
from program.types import (
    ArchivedEvidenceResponseType,
    ArchivedProgramType,
    ArchivedTaskType,
    ProgramCertificatesType,
    ProgramDetailType,
    ProgramResponseType,
    ProgramTasksType,
    ProgramType,
    SubTaskType,
    TaskTierType,
    TaskType,
    map_archived_evidence,
)
from program.utils.program_progress import get_program_progress
from program.utils.status import (
    get_locked_progress,
    get_tasks_progress,
    get_unlocked_progress,
)


def get_tasks_associated_controls(organization_id, tasks):
    safer_tasks = tasks or []
    controls = []
    for t in safer_tasks:
        associated_controls = t.get('associated_controls')

        if associated_controls:
            task_controls = Control.objects.filter(
                organization_id=organization_id, id__in=associated_controls
            )
            controls += task_controls

    return controls


class Mutation(graphene.ObjectType):
    create_task = CreateTask.Field()
    update_task = UpdateTask.Field()
    update_task_notes = UpdateTaskNotes.Field()
    create_subtask = CreateSubTask.Field()
    update_subtask = UpdateSubTask.Field()
    delete_subtask = DeleteSubTask.Field()
    add_subtask_evidence = AddSubTaskEvidence.Field()
    delete_subtask_evidence = DeleteSubTaskEvidence.Field()
    update_program = UpdateProgram.Field()
    update_subtask_status = UpdateSubTaskStatus.Field()
    update_subtask_due_date = UpdateSubTaskDueDate.Field()
    update_subtask_assignee = UpdateSubTaskAssignee.Field()


class Query(object):
    archived_programs = graphene.List(ArchivedProgramType)
    archived_program = graphene.Field(
        ArchivedProgramType, id=graphene.UUID(required=True)
    )
    archived_tasks = graphene.List(ArchivedTaskType, id=graphene.UUID(required=True))
    programs = graphene.List(ProgramType)
    organization_programs = graphene.Field(
        graphene.List(ProgramType), id=graphene.UUID(required=True)
    )
    program_detail = graphene.Field(ProgramDetailType, id=graphene.UUID(required=True))
    program_certificates = graphene.Field(
        ProgramCertificatesType, id=graphene.UUID(required=True)
    )
    program_tasks = graphene.Field(ProgramTasksType, id=graphene.UUID(required=True))
    task = graphene.Field(TaskType, id=graphene.UUID(required=True))

    task_controls = graphene.List(ControlType, id=graphene.UUID(required=True))

    subtask = graphene.Field(SubTaskType, id=graphene.UUID(required=True))

    archived_evidence = graphene.Field(
        ArchivedEvidenceResponseType, task_id=graphene.UUID(required=True)
    )

    @login_required
    @service_exception('Cannot get archived programs')
    def resolve_archived_programs(self, info, **kwargs):
        organization = info.context.user.organization
        return ArchivedProgram.objects.filter(organization=organization)

    @login_required
    @service_exception('Cannot get archived program')
    def resolve_archived_program(self, info, **kwargs):
        return ArchivedProgram.objects.get(
            id=kwargs.get('id'), organization=info.context.user.organization
        )

    @login_required
    @service_exception('Cannot get archived tasks')
    def resolve_archived_tasks(self, info, **kwargs):
        return ArchivedTask.objects.filter(
            program=kwargs.get('id'),
            program__organization=info.context.user.organization,
        )

    @login_required
    @service_exception('Cannot get programs')
    def resolve_programs_legacy(self, info, **kwargs):
        organization_id = info.context.user.organization_id

        programs = get_programs(organization_id)
        programs_data = []
        for p in programs:
            program_id = p.get('id')

            tasks = get_tasks_by_program(organization_id, program_id)
            controls = get_tasks_associated_controls(organization_id, tasks)

            tasks_progress = get_tasks_progress(tasks)
            controls_progress = get_progress(controls)

            is_locked = p.get('is_locked')

            progress = (
                get_locked_progress(controls_progress)
                if is_locked
                else get_unlocked_progress(tasks_progress)
            )

            programs_data.append({'id': program_id, 'progress': progress})

        return programs_data

    @login_required
    @service_exception('Cannot get program')
    def resolve_program_legacy(self, info, **kwargs):
        id = kwargs.get('id')
        organization = info.context.user.organization

        is_beta_policy_enabled = organization.feature_flags.filter(
            name='betaPolicyFeatureFlag', is_enabled=True
        ).exists()

        if is_beta_policy_enabled:
            policies = organization.policies.all()
            total = organization.policies.count()
            done = organization.policies.filter(is_published=True).count()
        else:
            policies = get_policies(organization.id)
            total = len(policies)
            done = len([p for p in policies if p.get('is_published')])

        policies_progress = {'id': 'policies', 'total': total, 'done': done}

        tasks = get_tasks_by_program(organization.id, id)
        tasks_progress = get_tasks_progress(tasks)

        controls = get_tasks_associated_controls(organization.id, tasks)
        controls_progress = get_progress(controls)

        return {
            'status': {
                'tasks': tasks_progress,
                'controls': controls_progress,
                'policies': policies_progress,
            }
        }

    @login_required
    @service_exception('Failed to get programs. Please try again.')
    @permission_required('program.view_program')
    def resolve_programs(self, info):
        return Program.objects.filter(
            organization=info.context.user.organization
        ).order_by('sort_index')

    @concierge_service(
        permission='user.view_concierge',
        exception_msg='''
        Failed to retrieve organization playbooks. Permission denied.''',
        revision_name='Can view concierge',
    )
    @service_exception('Failed to retrieve organization playbooks')
    def resolve_organization_programs(self, info, **kwargs):
        org_id = kwargs.get('id')
        return Program.objects.filter(organization__id=org_id).order_by('sort_index')

    @login_required
    @service_exception('Failed to get program details. Please try again.')
    @permission_required('program.view_program')
    def resolve_program_detail(self, info, **kwargs):
        return Program.objects.get(
            id=kwargs.get('id'), organization_id=info.context.user.organization_id
        )

    @login_required
    @service_exception('Failed to get program certificates. Please try again.')
    @permission_required('program.view_program')
    def resolve_program_certificates(self, info, **kwargs):
        return Program.objects.get(
            id=kwargs.get('id'), organization_id=info.context.user.organization_id
        )

    @login_required
    @service_exception('Failed to get program tasks. Please try again.')
    @permission_required('program.view_program')
    def resolve_program_tasks(self, info, **kwargs):
        program = Program.objects.get(
            id=kwargs.get('id'), organization_id=info.context.user.organization_id
        )

        tiers = []
        cache_name = (
            f'program_progress_{program.id}_organization_{program.organization.id}'
        )
        progress, unlocked_subtasks, completed_subtasks = get_program_progress(
            program, SubTask, cache_name=cache_name, force_update=True
        )
        task_ids = [unlocked_subtask.task_id for unlocked_subtask in unlocked_subtasks]
        visible_tasks = Task.objects.filter(id__in=task_ids)
        for index, t in enumerate(
            [GETTING_STARTED_TIER, NEXT_STEPS_TIER, FINISH_LINE_TIER]
        ):
            tasks_in_tier = [task for task in visible_tasks if task.tier == t]
            tiers.append(TaskTierType(id=index, name=t, tasks=tasks_in_tier))

        return ProgramResponseType(program=program, tasks=tiers)

    @login_required
    @service_exception('Failed to get task details. Please try again.')
    @permission_required('program.view_task')
    def resolve_task(self, info, **kwargs):
        task = Task.objects.get(
            id=kwargs.get('id'), program__organization=info.context.user.organization
        )
        program = task.program
        cache_name = (
            f'program_progress_{program.id}_organization_{program.organization.id}'
        )
        get_program_progress(program, SubTask, cache_name=cache_name, force_update=True)
        return task

    @login_required
    @service_exception('Failed to get task details. Please try again.')
    @permission_required('program.view_task')
    def resolve_task_controls(self, info, **kwargs):
        task = Task.objects.get(
            id=kwargs.get('id'), program__organization=info.context.user.organization
        )
        cache_name = (
            f'all_unlocked_subtasks_for_task_{task.id}'
            f'_organization_{task.program.organization.id}'
        )
        all_unlocked_subtasks = task.get_all_unlocked_subtasks(cache_name=cache_name)
        subtask_ids = all_unlocked_subtasks.values_list('id')
        unlocked_certificates = task.unlocked_certificates.values_list(
            'certification_id', flat=True
        )
        certification_sections_ids = CertificationSection.objects.filter(
            id__in=SubTask.objects.filter(id__in=subtask_ids).values_list(
                'certification_sections', flat=True
            ),
            certification_id__in=unlocked_certificates,
        ).values_list('id', flat=True)

        controls = (
            Control.objects.filter(
                organization=info.context.user.organization,
                certification_sections__id__in=certification_sections_ids,
            )
            .distinct()
            .order_by('display_id')
        )

        return controls

    @login_required
    @service_exception('Failed to get subtask details. Please try again.')
    @permission_required('program.view_task')
    def resolve_subtask(self, info, **kwargs):
        return SubTask.objects.get(
            id=kwargs.get('id'),
            task__program__organization=info.context.user.organization,
        )

    @login_required
    @service_exception('Cannot get documents')
    @permission_required('program.view_archivedevidence')
    def resolve_archived_evidence(self, info, **kwargs):
        task_id = kwargs.get('task_id')
        all_archived_evidence = ArchivedEvidence.objects.filter(
            organization=info.context.user.organization, archived_task__id=task_id
        )
        evidence_collection = map_archived_evidence(all_archived_evidence)
        return ArchivedEvidenceResponseType(
            task_id=task_id,
            collection=evidence_collection,
        )

from django.db.models import Count, F
from promise import Promise
from promise.dataloader import DataLoader

from certification.models import Certification, CertificationSection
from control.models import Control, ControlCertificationSection
from laika.data_loaders import ContextDataLoader
from program.constants import SUBTASK_COMPLETED_STATUS
from program.models import SubTask
from program.utils.program_progress import get_program_progress


class ProgramLoaders:
    def __init__(self, context):
        self.certificate_progress = CertificateProgressLoader.with_context(context)
        self.task_certificates = TaskCertificatesLoader.with_context(context)
        self.task_progress = TaskProgressLoader()
        self.task_badge = TaskBadgeLoader()
        self.task_assignees = TaskAssigneesLoader()


class CertificateProgressLoader(ContextDataLoader):
    def batch_load_fn(self, keys: list) -> Promise:
        organization = self.context.user.organization
        all_certification_sections = (
            CertificationSection.objects.prefetch_related('certification')
            .filter(certification_id__in=keys)
            .distinct()
        )

        implemented_controls_related = (
            ControlCertificationSection.objects.prefetch_related(
                'certification_section'
            )
            .filter(
                certification_section_id__in=all_certification_sections,
                control_id__in=Control.objects.filter(
                    organization=organization, status='IMPLEMENTED'
                ).distinct(),
            )
            .distinct()
        )

        all_controls_related = (
            Control.objects.filter(
                organization=organization,
                certification_sections__in=all_certification_sections,
            )
            .values(certificate_id=F('certification_sections__certification_id'))
            .annotate(count=Count('certification_sections__certification_id'))
        )
        related_controls_count = {
            control['certificate_id']: control['count']
            for control in all_controls_related
        }
        progress_by_certificate_id = {}

        for certification_key in keys:
            certificate_sections = [
                section.id
                for section in all_certification_sections
                if section.certification.id == certification_key
            ]

            implemented_controls = [
                related_control.id
                for related_control in implemented_controls_related
                if related_control.certification_section.id in certificate_sections
            ]
            total_controls = related_controls_count.get(certification_key, 0)

            progress_by_certificate_id[certification_key] = (
                0
                if not total_controls
                else len(implemented_controls) / total_controls * 100
            )

        return Promise.resolve(
            [progress_by_certificate_id.get(certificate_id) for certificate_id in keys]
        )


class TaskCertificatesLoader(ContextDataLoader):
    def batch_load_fn(self, keys: list) -> Promise:
        organization = self.context.user.organization
        certifications = (
            Certification.objects.filter(
                unlocked_organizations__organization=organization,
                sections__subtaskcertificationsection__subtask__task_id__in=keys,
            )
            .values_list('name')
            .distinct()
        )
        return Promise.resolve([certifications for _ in keys])


def get_tasks(program):
    cache_name = f'program_progress_{program.id}_organization_{program.organization.id}'
    progress, unlocked_subtasks, completed_subtasks = get_program_progress(
        program, SubTask, cache_name=cache_name
    )
    tasks = {}
    for subtask in unlocked_subtasks:
        task_id = subtask.task_id
        total_not_applied_subtasks = 0
        total_subtasks, completed_subtask_count, badges = tasks.get(task_id, (0, 0, []))
        total_subtasks += 1
        new_badges = subtask.badges.split(',') if subtask.badges else []
        if subtask.status == SUBTASK_COMPLETED_STATUS:
            completed_subtask_count += 1
        if subtask.status == 'not_applicable':
            total_not_applied_subtasks += 1
        tasks[task_id] = (
            total_subtasks - total_not_applied_subtasks,
            completed_subtask_count,
            set(list(badges) + new_badges),
        )
    return tasks


def map_task_progress(task):
    total_subtasks, completed_subtasks, _ = task
    return 100 if total_subtasks == 0 else (completed_subtasks / total_subtasks) * 100


class TaskProgressLoader(DataLoader):
    @staticmethod
    def batch_load_fn(tasks: list) -> Promise:
        grouped_tasks = get_tasks(tasks[0].program)
        return Promise.resolve(
            [
                map_task_progress(grouped_tasks.get(task.id, (0, 0, [])))
                for task in tasks
            ]
        )


class TaskBadgeLoader(DataLoader):
    @staticmethod
    def batch_load_fn(tasks: list) -> Promise:
        grouped_tasks = get_tasks(tasks[0].program)
        badge_index = 2

        return Promise.resolve(
            [grouped_tasks.get(task.id, (0, 0, []))[badge_index] for task in tasks]
        )


class TaskAssigneesLoader(DataLoader):
    @staticmethod
    def batch_load_fn(tasks):
        program = tasks[0].program
        cache_name = (
            f'program_progress_{program.id}_organization_{program.organization.id}'
        )
        _, unlocked_subtasks, _ = get_program_progress(
            tasks[0].program, SubTask, cache_name=cache_name
        )
        assignees_by_task = {}

        for subtask in unlocked_subtasks:
            task_id = subtask.task.id
            assignees, seen_ids = assignees_by_task.get(task_id, ([], []))
            if subtask.assignee and subtask.assignee.id not in seen_ids:
                assignees.append(subtask.assignee)
                seen_ids.append(subtask.assignee.id)
            assignees_by_task[task_id] = (assignees, seen_ids)

        return Promise.resolve(
            [assignees_by_task.get(task.id, ([], []))[0] for task in tasks]
        )

from typing import Any, List, Tuple

from django.db.models import Q

from evidence.models import Evidence, SystemTagEvidence
from laika.cache import cache_func
from program.constants import SUBTASK_COMPLETED_STATUS
from tag.models import Tag


def get_excluded_subtask_ids(organization, unlocked_subtasks_ids, unlocked_subtasks):
    evidences = Evidence.objects.prefetch_related('system_tags').filter(
        Q(organization=organization)
        & (
            Q(system_tags__name__in=unlocked_subtasks_ids)
            | Q(system_tags__in=Tag.objects.filter(name__in=unlocked_subtasks_ids))
        )
    )
    evidence_tags = SystemTagEvidence.objects.filter(
        evidence__in=evidences
    ).values_list('tag__name', flat=True)
    exclude_by_complexity_ids = []
    subtasks_by_group = set()
    complexity_subtasks = unlocked_subtasks.exclude(
        complexity_group__isnull=True
    ).exclude(complexity_group__exact='')
    for subtask in complexity_subtasks:
        key = f'{subtask.task_id}-{subtask.complexity_group}'
        if key in subtasks_by_group and str(subtask.id) not in evidence_tags:
            exclude_by_complexity_ids.append(subtask.id)
            continue
        subtasks_by_group.add(key)
    return exclude_by_complexity_ids


def get_subtasks_progress(organization, unlocked_subtasks, user_subtasks):
    unlocked_subtasks_ids = [str(subtask.id) for subtask in unlocked_subtasks]
    exclude_by_complexity_ids = get_excluded_subtask_ids(
        organization, unlocked_subtasks_ids, unlocked_subtasks
    )

    visible_subtasks = list(user_subtasks) + list(
        unlocked_subtasks.exclude(id__in=exclude_by_complexity_ids)
    )
    visible_not_applicable_subtasks = list(
        unlocked_subtasks.filter(status='not_applicable')
    ) + list(user_subtasks.filter(status='not_applicable'))
    completed_subtasks = list(
        unlocked_subtasks.filter(status=SUBTASK_COMPLETED_STATUS)
    ) + list(user_subtasks.filter(status=SUBTASK_COMPLETED_STATUS))

    visible_subtasks_count = len(visible_subtasks)
    visible_not_applicable_subtasks_count = len(visible_not_applicable_subtasks)
    completed_subtasks_count = len(completed_subtasks)
    subtasks_count = visible_subtasks_count - visible_not_applicable_subtasks_count
    total_subtasks = 1 if subtasks_count == 0 else subtasks_count
    if visible_subtasks_count == 0:
        return 0, [], []

    progress = completed_subtasks_count / total_subtasks * 100

    return (progress, visible_subtasks, completed_subtasks)


@cache_func
def get_program_progress(
    program, subtask_model, **kwargs
) -> Tuple[int, List[Any], List[Any]]:
    certificate_ids = program.unlocked_certificate_ids
    unlocked_subtasks = (
        subtask_model.objects.filter(
            task__program=program,
            certification_sections__certification_id__in=certificate_ids,
        )
        .order_by('-complexity', 'complexity_group')
        .distinct()
    )
    user_subtasks = subtask_model.objects.filter(
        task__program=program, is_system_subtask=False
    )
    return get_subtasks_progress(program.organization, unlocked_subtasks, user_subtasks)

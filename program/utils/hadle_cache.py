import logging

from django.core.cache import cache

from laika.celery import app as celery_app

logger = logging.getLogger('program_tasks')


@celery_app.task(name='Program cache update')
def trigger_program_cache(organization_id: str):
    from organization.models import Organization

    organization = Organization.objects.get(id=organization_id)

    logger.info(
        f'Updating playbooks cache for org: {organization.id}, '
        f' name: {organization.name}'
    )

    trigger_program_progress_cache(organization)
    trigger_program_certificates_cache(organization)
    trigger_program_visible_tasks_cache(organization)
    trigger_unlocked_tasks_cache(organization)

    logger.info(
        f'Playbooks Cache updated successfully for organization: {organization.id}'
        f' name: {organization.name}'
    )


def trigger_program_progress_cache(organization, action='CREATE'):
    # Updating program progress
    from program.models import SubTask
    from program.utils.program_progress import get_program_progress

    programs = organization.programs.all()
    for p in programs:
        logger.info(f'Updating cache for program {p.id} progress')
        cache_name = f'program_progress_{p.id}_organization_{p.organization.id}'
        if action == 'CREATE':
            get_program_progress(p, SubTask, cache_name=cache_name, force_update=True)
        else:
            cache.delete(cache_name)


def trigger_program_certificates_cache(organization, action='CREATE'):
    # Updating visible certificates for program
    programs = organization.programs.all()
    for p in programs:
        logger.info(
            f'Updating cache for program {p.id}, organization: {organization.id}'
        )
        if action == 'CREATE':
            p.get_all_certificates(
                cache_name=(
                    f'certificates_for_program_{p.id}_organization_{organization.id}'
                ),
                force_update=True,
            )
        else:
            cache.delete(
                f'certificates_for_program_{p.id}_organization_{organization.id}'
            )


def trigger_program_visible_tasks_cache(organization, action='CREATE'):
    # Updating visible tasks for program
    programs = organization.programs.all()
    for p in programs:
        if action == 'CREATE':
            p.get_visible_tasks(
                cache_name=f'visible_tasks_{p.id}_organization_{organization.id}',
                force_update=True,
            )
        else:
            cache.delete(f'visible_tasks_{p.id}_organization_{organization.id}')


def trigger_unlocked_tasks_cache(organization, action='CREATE'):
    # Updating all unlocked subtasks for tasks in program
    programs = organization.programs.all()
    for p in programs:
        tasks = p.tasks.all()
        for t in tasks:
            if action == 'CREATE':
                t.get_all_unlocked_subtasks(
                    cache_name=(
                        f'all_unlocked_subtasks_for_task_{t.id}'
                        f'_organization_{organization.id}'
                    ),
                    force_update=True,
                )
                t.get_unlocked_subtasks(
                    cache_name=(
                        f'unlocked_subtasks_for_task_{t.id}'
                        f'_organization_{organization.id}'
                    ),
                    force_update=True,
                )
            else:
                cache.delete(
                    f'all_unlocked_subtasks_for_task_{t.id}'
                    f'_organization_{organization.id}'
                )
                cache.delete(
                    f'unlocked_subtasks_for_task_{t.id}_organization_{organization.id}'
                )

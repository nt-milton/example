import logging

from laika.celery import app as celery_app
from organization.models import Organization
from program.utils.hadle_cache import (
    trigger_program_certificates_cache,
    trigger_program_progress_cache,
    trigger_program_visible_tasks_cache,
    trigger_unlocked_tasks_cache,
)

logger = logging.getLogger('program_tasks')


@celery_app.task(name='Cache Organization Programs')
def refresh_organization_cache(*args, **kwargs):
    if not args or not args[0]:
        return
    organization = Organization.objects.get(id=args[0])
    try:
        logger.info(f'Updating cache for organization {organization.id}')

        trigger_program_progress_cache(organization, action=kwargs.get('action'))
        trigger_program_certificates_cache(organization, action=kwargs.get('action'))
        trigger_program_visible_tasks_cache(organization, action=kwargs.get('action'))
        trigger_unlocked_tasks_cache(organization, action=kwargs.get('action'))

        logger.info(f'Cache successfully updated for  {organization.id}')
        return {'success': True}
    except Exception as e:
        logger.error(
            f'Error refreshing programs for organization {organization.id}. {e}'
        )

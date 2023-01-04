import logging

from blueprint.models import ControlBlueprint
from blueprint.prescribe import (
    create_prescription_history_entry_controls_prescribed,
    prescribe_controls,
)
from certification.models import Certification, UnlockedOrganizationCertification
from laika.celery import app as celery_app
from organization.constants import (
    HISTORY_STATUS_FAILED,
    HISTORY_STATUS_IN_PROGRESS,
    HISTORY_STATUS_SUCCESS,
)
from organization.models import Organization
from user.models import User

logger = logging.getLogger(__name__)


@celery_app.task(
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2},
    retry_backoff=True,
    name='Control Prescription',
)
def do_prescribe_controls(
    organization_id: str, user_id: str, control_ref_ids: list[str]
):
    logger.info('Init control prescription task')

    try:
        organization = Organization.objects.get(id=organization_id)
        current_user = User.objects.get(id=user_id)
    except Exception as e:
        logger.warning(f'Error getting basic info when prescribing: {e}')
        return {'success': False}

    entry = create_prescription_history_entry_controls_prescribed(
        organization, current_user, control_ref_ids, HISTORY_STATUS_IN_PROGRESS
    )

    try:
        prescribe_controls(organization_id, control_ref_ids)
        entry.status = HISTORY_STATUS_SUCCESS
        entry.save()
    except Exception as e:
        logger.warning(f'Error prescribing controls: {e}')
        entry.status = HISTORY_STATUS_FAILED
        entry.save()
    return {'success': True}


@celery_app.task(
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2},
    retry_backoff=True,
    name='Prescribe Content Profiles',
)
def prescribe_content(user_id: str, organization_id: str, framework_tags: list[str]):
    logger.info(
        f'Init prescribing content for organization: {organization_id}, '
        f'user: {user_id}, tags: {framework_tags}'
    )

    for tag in framework_tags:
        reference_ids = list(
            ControlBlueprint.objects.filter(reference_id__endswith=tag).values_list(
                'reference_id', flat=True
            )
        )

        certification = Certification.objects.get(code=tag)

        if not reference_ids:
            continue

        entry = create_prescription_history_entry_controls_prescribed(
            Organization.objects.get(id=organization_id),
            User.objects.get(id=user_id),
            reference_ids,
            HISTORY_STATUS_IN_PROGRESS,
        )

        try:
            logger.info(
                f'Try prescribing content for organization: {organization_id}, '
                f'user: {user_id}, tag: {tag}, controls: {reference_ids}'
            )

            if not UnlockedOrganizationCertification.objects.filter(
                certification_id=certification.id, organization_id=organization_id
            ).exists():
                UnlockedOrganizationCertification.objects.create(
                    organization_id=organization_id, certification_id=certification.id
                )

            prescribe_controls(organization_id, reference_ids)
            logger.info(
                f'Content prescribed successfully for organization: {organization_id},'
                f' user: {user_id}, tag: {tag}, controls: {reference_ids}'
            )

            entry.status = HISTORY_STATUS_SUCCESS
            entry.save()
        except Exception as e:
            logger.warning(
                f'Error prescribing content for organization: {organization_id}, '
                f'user: {user_id}, tag: {tag}, controls: {reference_ids}, error: {e}'
            )
            entry.status = HISTORY_STATUS_FAILED
            entry.save()
    return {'success': True}

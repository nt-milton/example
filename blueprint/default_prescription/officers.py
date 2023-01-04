import logging

from blueprint.models.officer import OfficerBlueprint
from organization.models import Organization
from user.models import Officer

logger = logging.getLogger(__name__)


def prescribe(organization: Organization) -> list[str]:
    status_detail = []
    for officer_blueprint in OfficerBlueprint.objects.iterator():
        try:
            new_officer, _ = Officer.objects.update_or_create(
                organization=organization,
                name=officer_blueprint.name,
                defaults={
                    'description': officer_blueprint.description,
                },
            )

            logger.info(
                f'New officer {new_officer} created for organization: {organization}'
            )
        except Exception as e:
            error_message = f'Error prescribing {officer_blueprint}: {e}'
            status_detail.append(error_message)
            logger.warning(error_message)
    return status_detail

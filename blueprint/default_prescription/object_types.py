import logging

from blueprint.models.object import ObjectBlueprint
from objects.models import LaikaObjectType
from organization.models import Organization

logger = logging.getLogger(__name__)


def prescribe(organization: Organization) -> list[str]:
    status_detail = []
    for object_blueprint in ObjectBlueprint.objects.iterator():
        try:
            new_object, _ = LaikaObjectType.objects.update_or_create(
                organization=organization,
                type_name=object_blueprint.type_name,
                defaults={
                    'display_name': object_blueprint.display_name,
                    'color': object_blueprint.color,
                    'icon_name': object_blueprint.icon_name,
                    'display_index': object_blueprint.display_index,
                    'is_system_type': object_blueprint.is_system_type,
                    'description': object_blueprint.description,
                },
            )

            logger.info(
                f'New object type {new_object} created for organization: {organization}'
            )
        except Exception as e:
            error_message = f'Error prescribing {object_blueprint}: {e}'
            status_detail.append(error_message)
            logger.warning(error_message)
    return status_detail

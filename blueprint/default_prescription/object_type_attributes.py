import logging

from blueprint.models.object_attribute import ObjectAttributeBlueprint
from objects.metadata import Metadata
from objects.models import Attribute, LaikaObjectType
from organization.models import Organization

logger = logging.getLogger(__name__)


def prescribe(organization: Organization) -> list[str]:
    status_detail = []
    for obj_attr_blueprint in ObjectAttributeBlueprint.objects.iterator():
        try:
            object_type = LaikaObjectType.objects.get(
                organization=organization, type_name=obj_attr_blueprint.object_type_name
            )

            new_attribute, _ = Attribute.objects.update_or_create(
                object_type=object_type,
                name=obj_attr_blueprint.name,
                defaults={
                    'sort_index': obj_attr_blueprint.display_index,
                    'attribute_type': obj_attr_blueprint.attribute_type,
                    'min_width': obj_attr_blueprint.min_width,
                    'is_required': obj_attr_blueprint.is_required,
                    '_metadata': get_metadata(obj_attr_blueprint).to_json(),
                },
            )

            logger.info(
                f'New object type attribute {new_attribute} created for '
                f'organization: {organization}'
            )
        except Exception as e:
            error_message = f'Error prescribing {obj_attr_blueprint}: {e}'
            status_detail.append(error_message)
            logger.warning(error_message)
    return status_detail


def get_metadata(object_attribute_blueprint):
    attribute = Attribute()
    attribute.attribute_type = object_attribute_blueprint.attribute_type
    attribute.name = object_attribute_blueprint.name
    default_value = object_attribute_blueprint.default_value
    metadata = Metadata()
    metadata.is_protected = object_attribute_blueprint.is_protected
    metadata.default_value = default_value
    metadata.set_select_options_from_csv(object_attribute_blueprint.select_options)
    return metadata

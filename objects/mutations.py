import base64
import io
import logging

import graphene
import reversion
from openpyxl import load_workbook

from laika.decorators import laika_service
from laika.types import UploadResultType
from laika.utils.exceptions import ServiceException
from objects.inputs import ObjectFileInput
from objects.types import AttributeTypeFactory
from objects.utils import (
    link_lo_background_check_with_user,
    process_object_data,
    unlink_lo_background_check_with_user,
)

from .inputs import (
    BulkDeleteLaikaObjectsInput,
    LaikaObjectInput,
    UpdateLaikaObjectInput,
)
from .models import LaikaObject
from .models import LaikaObjectType as LaikaObjectTypeModel
from .system_types import BackgroundCheck

logger = logging.getLogger('objects')


class CreateLaikaObject(graphene.Mutation):
    class Arguments:
        input = LaikaObjectInput(required=True)

    id = graphene.Int()
    warnings = graphene.List(graphene.String, default_value=[])

    @laika_service(
        permission='objects.add_laikaobject',
        revision_name='Created new Laika Object',
        exception_msg='Cannot create new Laika Object',
    )
    def mutate(self, info, input):
        laika_object_type = LaikaObjectTypeModel.objects.get(
            organization=info.context.user.organization, id=input.laika_object_type
        )
        clean_data, failing_fields = pick_type_attributes_only(
            laika_object_type,
            input.laika_object_data,
        )
        new_laika_object = LaikaObject.objects.create(
            object_type=laika_object_type, data=clean_data, is_manually_created=True
        )

        warnings = (
            [
                'New Laika Object added with incomplete fields: '
                f'{", ".join(failing_fields)}'
            ]
            if failing_fields
            else []
        )

        return CreateLaikaObject(id=new_laika_object.id, warnings=warnings)


def pick_type_attributes_only(
    laika_object_type,
    laika_object_data,
):
    """Select only existing attributes in the Laika Object Type

    Returns a tuple containing:
    - a dict of attribute name and value
    - a list of attributes that failed validation
    """
    attributes = {}
    failing_fields = []
    for attribute in laika_object_type.attributes.order_by('sort_index'):
        attribute_type = AttributeTypeFactory.get_attribute_type(attribute)
        attribute_value = laika_object_data.get(
            attribute.name, attribute_type.get_default_value()
        )
        try:
            attribute_type.validate(attribute_value)
        except ValueError:
            failing_fields.append(attribute.name)
            attributes[attribute.name] = None
            logger.warning(
                'Incorrect value "%s" for attribute "%s" with type "%s"'
                ' in object type id "%s"',
                attribute_value,
                attribute.name,
                attribute.attribute_type,
                laika_object_type.id,
            )
        else:
            attributes[attribute.name] = attribute_value

    return attributes, failing_fields


class UpdateLaikaObject(graphene.Mutation):
    class Arguments:
        input = UpdateLaikaObjectInput(required=True)

    id = graphene.Int()

    @laika_service(
        permission='objects.change_laikaobject',
        revision_name='Updated Laika Object',
        exception_msg='Cannot update Laika Object',
    )
    def mutate(self, info, input):
        laika_object = LaikaObject.objects.get(
            id=input.laika_object_id,
            object_type__organization=info.context.user.organization,
        )

        laika_object_type = laika_object.object_type
        new_data = input.laika_object_data
        clean_data = {}
        for attribute in laika_object_type.attributes.all():
            name = attribute.name
            if name in new_data:
                attribute_type = AttributeTypeFactory.get_attribute_type(attribute)
                attribute_type.validate(new_data[name])
                clean_data[name] = new_data[name]
                if name == BackgroundCheck.link_people_table.display_name:
                    if laika_object.data.get(
                        BackgroundCheck.link_people_table.display_name
                    ):
                        unlink_lo_background_check_with_user(
                            laika_objects=[laika_object]
                        )
                    link_lo_background_check_with_user(
                        new_data[name], laika_object.data.get('People Status')
                    )

        laika_object.data.update(clean_data)
        laika_object.save()

        return UpdateLaikaObject(id=laika_object.id)


class BulkDeleteLaikaObjects(graphene.Mutation):
    class Arguments:
        input = BulkDeleteLaikaObjectsInput(required=True)

    deleted_ids = graphene.List(graphene.String)

    @laika_service(
        permission='objects.delete_laikaobject',
        exception_msg='Deleting Laika objects have failed',
    )
    def mutate(self, info, input=None):
        if not input.laika_object_ids:
            return BulkDeleteLaikaObjects(input.laika_object_ids)

        with reversion.create_revision():
            reversion.set_comment('Deleted Laika Objects')
            reversion.set_user(info.context.user)

            laika_objects = LaikaObject.objects.filter(
                id__in=input.laika_object_ids,
                object_type__organization=info.context.user.organization,
            )
            if laika_objects:
                unlink_lo_background_check_with_user(laika_objects=laika_objects)
                laika_objects.delete()

        logger.info(
            f'Laika objects ids {input.laika_object_ids} in '
            f'organization {info.context.user.organization} '
            'were deleted'
        )

        return BulkDeleteLaikaObjects(input.laika_object_ids)


class BulkUploadObject(graphene.Mutation):
    class Arguments:
        input = ObjectFileInput(required=True)

    upload_result = graphene.List(UploadResultType, default_value=[])

    @laika_service(
        permission='objects.bulk_upload_object',
        exception_msg='Failed to upload Object file. Please try again.',
    )
    def mutate(self, info, input):
        object_file = input.object_file

        if not object_file.file_name.endswith('.xlsx'):
            raise ServiceException(
                'Invalid upload object file type. File must be .xlsx'
            )

        workbook = load_workbook(io.BytesIO(base64.b64decode(object_file.file)))

        upload_result = process_object_data(
            info.context.user,
            workbook,
        )

        return BulkUploadObject(upload_result=upload_result)

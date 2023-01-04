import logging
from datetime import datetime
from typing import Dict, Union

from django.apps import apps
from django.db import transaction
from django.db.models import F, Q

from alert.constants import ALERT_TYPE_USER, ALERT_TYPES
from laika.types import UploadResultType
from laika.utils.paginator import get_paginated_result
from objects.models import LaikaObject, LaikaObjectType
from objects.types import AttributeTypeFactory, Types
from program.utils.alerts import create_alert
from seeder.seeders.commons import are_columns_empty, get_formatted_headers
from user.constants import ROLE_ADMIN, ROLE_SUPER_ADMIN
from user.models import (
    BACKGROUND_CHECK_STATUS_NA,
    BACKGROUND_CHECK_STATUS_PASSED,
    BACKGROUND_CHECK_STATUS_PENDING,
    User,
)

from .constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from .system_types import BACKGROUND_CHECK

logger = logging.getLogger('objects')

ATTRIBUTE_ORDER = 'sort_index'
HEADER_ROW = 2
OBJECTS_START = 3

BACKGROUND_CHECK_TYPE = 'BGC'


def map_row_to_dic(row, headers):
    return dict(zip(headers, [entry for entry in row]))


def process_object_data(updated_by, workbook):
    organization = updated_by.organization
    laika_object_types = LaikaObjectType.objects.filter(
        organization=organization, type_name__in=workbook.sheetnames
    )

    upload_result = []
    for laika_object_type in laika_object_types:
        attribute_types = get_attribute_types(laika_object_type)
        sheet = workbook[laika_object_type.type_name]
        headers = [cell.value for cell in sheet[HEADER_ROW] if cell.value]

        if set(headers) != set(attribute_types.keys()):
            upload_result.append(
                UploadResultType(
                    title=laika_object_type.display_name,
                    icon_name=laika_object_type.icon_name,
                    icon_color=laika_object_type.color,
                    message='Upload Failed: Incorrect headers',
                )
            )
            logger.warning(
                'Incorrect headers in bulk upload for organization: '
                f'{organization.id} and sheet: {sheet.title}.'
            )
            continue

        failed_rows, success_rows = process_rows(
            attribute_types, headers, laika_object_type, organization, sheet
        )

        if failed_rows or success_rows:
            upload_result.append(
                UploadResultType(
                    title=laika_object_type.display_name,
                    icon_name=laika_object_type.icon_name,
                    icon_color=laika_object_type.color,
                    successful_rows=success_rows,
                    failed_rows=failed_rows,
                )
            )

    return upload_result


def process_rows(attribute_types, headers, laika_object_type, organization, sheet):
    success_rows = 0
    failed_rows = []
    for row in sheet.iter_rows(min_row=OBJECTS_START):
        try:
            with transaction.atomic():
                row_values = [cell.value for cell in row]
                row_dic = map_row_to_dic(row_values, get_formatted_headers(headers))

                if are_columns_empty(row_dic, attribute_types.keys()):
                    continue

                LaikaObject.objects.create(
                    data=get_formatted_data(attribute_types, row_dic),
                    object_type=laika_object_type,
                    is_manually_created=True,
                )
                success_rows += 1
        except Exception as ex:
            failed_rows.append(row[0].row)
            logger.warning(
                'Invalid object entry in bulk upload for organization: '
                f'{organization.id}. '
                f'Sheet: {sheet.title}, Row: {row[0].row}. '
                f'Error: {ex}'
            )
    return failed_rows, success_rows


def get_attribute_types(laika_object_type):
    attributes = laika_object_type.attributes.all().order_by(ATTRIBUTE_ORDER)
    attribute_types = {}
    for attribute in attributes:
        attribute_type = AttributeTypeFactory.get_attribute_type(attribute)
        attribute_types[attribute_type.get_export_header()] = attribute_type
    return attribute_types


def get_formatted_data(attribute_types, row_dic):
    data = {}
    for header_name, attribute_type in attribute_types.items():
        row_value = None
        if header_name in row_dic:
            row_value = row_dic.get(header_name)
        formatted_value = attribute_type.format(row_value)
        attribute_type.validate(formatted_value)
        data[attribute_type.attribute.name] = formatted_value
    return data


def update_objects_with_user(user):
    objects_to_update = []
    object_types = LaikaObjectType.objects.filter(organization=user.organization)
    for object_type in object_types:
        update_object_type(object_type, objects_to_update, user)

    LaikaObject.objects.bulk_update(objects_to_update, ['data'])

    return objects_to_update


def update_object_type(object_type, objects_to_update, user):
    user_info = user.as_dict()
    # Get only USER attributes for this object type
    attributes = object_type.attributes.filter(attribute_type=Types.USER.name)
    if not attributes:
        return

    filter_query = get_objects_filter(attributes, user.email, object_type)
    laika_objects = LaikaObject.objects.filter(filter_query)
    for laika_object in laika_objects:
        update_user_in_object(attributes, laika_object, user_info)
        objects_to_update.append(laika_object)


def update_user_in_object(attributes, laika_object, user_info):
    """Update user fields in Object only if the email match
    - attributes: list of User attributes inside the object
    - laika_object: to update
    - user_info: to get the email and other user info
    """
    for attribute in attributes:
        data_user = laika_object.data[attribute.name]
        if (
            data_user
            and data_user.get('email') == user_info['email']
            and data_user != user_info
        ):
            laika_object.data[attribute.name] = user_info


def get_objects_filter(attributes, email, object_type):
    """Filter objects for object type and USER attributes

    Filter where:
    - any of the USER attributes matches the email
    - object_type
    """
    query = Q()
    for attribute in attributes:
        query.add(Q(**{f'data__{attribute.name}__email': email}), Q.OR)
    query.add(Q(**{'object_type': object_type}), Q.AND)
    return query


def get_pagination_result(pagination, data):
    page = pagination.page if pagination else DEFAULT_PAGE
    page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE

    return get_paginated_result(data, page_size, page)


def get_order_by(order_by):
    return (
        F(order_by['field']).desc(nulls_last=True)
        if order_by['order'] == 'descend'
        else F(order_by['field']).asc(nulls_last=True)
    )


def build_bearer_header(access_token):
    return {"Authorization": f"Bearer {access_token}"}


def create_background_check_alerts(
    alert_related_object: Union[Dict[str, Union[LaikaObject, User]]] = None,
    alert_related_model: str = None,
    alert_type: str = None,
    organization_id: str = None,
):
    if alert_type not in ALERT_TYPES:
        logger.error(f'Alert type - {alert_type} is not valid')
        return
    alert_related_data = {}
    if alert_related_model is not None:
        try:
            related_model = apps.get_model(alert_related_model)
        except KeyError:
            logger.error(f'AlertRelatedModel - {alert_related_model} is not valid')
            return
        else:
            alert_related_data = {
                'alert_related_model': related_model,
                'alert_related_object': alert_related_object,
            }

    users_admin = User.objects.filter(organization=organization_id).filter(
        role__in=[ROLE_ADMIN, ROLE_SUPER_ADMIN]
    )
    for user in users_admin:
        create_alert(
            room_id=organization_id,
            receiver=user,
            alert_type=alert_type,
            sender_name='Admin',
            **alert_related_data,
        )
        logger.info(
            f'Alert type {alert_type} created in the model '
            f'{alert_related_model} for the user {user.id}'
        )


def find_user_match_and_create_alerts_for_background_check(
    first_name=None, last_name=None, email=None, organization_id=None
):
    if organization_id is None:
        logger.error('The organization should not be None')
        return

    user_matches = User.objects.filter(organization_id=organization_id).filter(
        Q(first_name__iexact=first_name, last_name__iexact=last_name) | Q(email=email)
    )
    num_matches = len(user_matches)
    if num_matches > 0:
        alert_type = ALERT_TYPE_USER.get(
            'LO_BACKGROUND_CHECK_SINGLE_MATCH_USER_TO_LO', ''
        )
        if num_matches > 1:
            alert_type = ALERT_TYPE_USER.get(
                'LO_BACKGROUND_CHECK_MULTIPLE_MATCH_USER_TO_LO', ''
            )
        create_background_check_alerts(
            alert_related_object={'user': user_matches[0]},
            alert_related_model='user.UserAlert',
            alert_type=alert_type,
            organization_id=organization_id,
        )


def unlink_lo_background_check_with_user(laika_objects=None):
    users_linked_to_lo = [
        lo.data.get("Link to People Table", {}).get('id')
        for lo in laika_objects
        if (
            lo.object_type.type_name == BACKGROUND_CHECK.type
            and lo.data.get("Link to People Table") is not None
        )
    ]
    User.objects.filter(id__in=users_linked_to_lo).update(
        background_check_passed_on=None,
        background_check_status=BACKGROUND_CHECK_STATUS_NA,
    )


def link_lo_background_check_with_user(user_email=None, bg_status=None):
    if user_email is None:
        return
    if bg_status is None:
        bg_status = BACKGROUND_CHECK_STATUS_PENDING
    fields = {'background_check_status': bg_status}
    if bg_status == BACKGROUND_CHECK_STATUS_PASSED:
        fields.update({'background_check_passed_on': datetime.today()})
    User.objects.filter(email=user_email).update(**fields)


def get_bgc_tray_keys():
    type_key = BACKGROUND_CHECK_TYPE
    description_key = BACKGROUND_CHECK_TYPE
    label_key = BACKGROUND_CHECK_TYPE
    return type_key, description_key, label_key

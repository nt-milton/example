from integration.tests import create_connection_account
from objects.models import Attribute, LaikaObject, LaikaObjectType
from organization.tests import create_organization
from user.tests.factory import create_user


def create_object_type(
    organization=None, display_name='', type_name='', color='', display_index=0
):
    if not organization:
        organization = create_organization(flags=[], name='org-test')

    return LaikaObjectType.objects.create(
        organization=organization,
        display_name=display_name,
        type_name=type_name,
        color=color,
        display_index=display_index,
    )


def create_attribute(
    object_type, name='', attribute_type=None, sort_index=0, metadata=None
):
    if metadata is None:
        metadata = {}

    return Attribute.objects.create(
        object_type=object_type,
        name=name,
        attribute_type=attribute_type,
        sort_index=sort_index,
        _metadata=metadata,
    )


def create_laika_object(
    object_type,
    connection_account,
    data={},
    **kwargs,
) -> LaikaObject:
    return LaikaObject.objects.create(
        object_type=object_type,
        connection_account=connection_account,
        data=data,
        **kwargs,
    )


def create_lo_with_connection_account(
    organization, object_type=None, data=None, vendor_name='vendor', **kwargs
):
    data = {} if data is None else data
    if object_type is None:
        type_name = kwargs.pop('type_name', '')
        object_type = create_object_type(organization, type_name=type_name)
    connection_account = create_connection_account(
        vendor_name,
        organization=organization,
        authentication={'checkr_account_id': ''},
        created_by=create_user(organization, email='heylaika1@heylaika.com'),
    )
    if type(data) is dict:
        lo = create_laika_object(object_type, connection_account, data, **kwargs)
        return lo, connection_account
    if type(data) is list:
        lo_result = []
        for lo_data in data:
            lo = create_laika_object(object_type, connection_account, lo_data, **kwargs)
            lo_result.append(lo)
        return lo_result, connection_account

import json
import logging

import graphene
from graphene_django.types import DjangoObjectType

from laika.decorators import laika_service
from laika.types import OrderInputType, PaginationInputType, PaginationResponseType
from laika.utils.dictionaries import exclude_dict_keys
from objects.mutations import (
    BulkDeleteLaikaObjects,
    CreateLaikaObject,
    UpdateLaikaObject,
)

from .inputs import LaikaObjectFilterType
from .models import Attribute, LaikaObject
from .models import LaikaObjectType as LaikaObjectTypeModel
from .mutations import BulkUploadObject
from .utils import get_order_by, get_pagination_result

logger = logging.getLogger(__name__)


class LaikaObjectDataType(DjangoObjectType):
    class Meta:
        model = LaikaObject
        description = (
            'A Laika Object. The object\'s data can be found in the `data` attribute'
        )


class LaikaObjectDataResponseType(graphene.ObjectType):
    class Meta:
        description = (
            'The Laika Objects returned by the query '
            'along with metadata describing the current'
            ' page and page size'
        )

    data = graphene.List(LaikaObjectDataType)
    pagination = graphene.Field(PaginationResponseType)


class LaikaAttributeType(DjangoObjectType):
    class Meta:
        model = Attribute
        description = 'A list of attributes contained within the object'


class LaikaObjectElementsIdsType(graphene.ObjectType):
    ids = graphene.List(graphene.String)


class LaikaObjectType(DjangoObjectType):
    class Meta:
        model = LaikaObjectTypeModel
        exclude = ('organization', 'is_system_type')
        description = 'A JSON representation of a Laika Object Type'

    attributes = graphene.List(LaikaAttributeType)
    elements = graphene.Field(
        LaikaObjectDataResponseType,
        order_by=graphene.Argument(OrderInputType, required=False),
        filter=graphene.List(LaikaObjectFilterType, required=False),
        pagination=graphene.Argument(PaginationInputType, required=False),
    )

    def resolve_attributes(self, info, **kwargs):
        return self.attributes.order_by('sort_index')

    def resolve_elements(self, info, **kwargs):
        filters = kwargs.get('filter', {})

        filter_query = self.get_incredible_filter_query(filters)

        order_by = kwargs.get('order_by', "")
        order_by = self.get_order_by(order_by)
        annotate = self.get_annotate(filters)

        data = (
            self.elements.filter(deleted_at=None)
            .annotate(**annotate)
            .filter(filter_query)
            .order_by(order_by)
        )
        paginated_result = get_pagination_result(
            pagination=kwargs.get('pagination'), data=data
        )

        return LaikaObjectDataResponseType(
            data=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )


class LaikaObjectsResponseType(graphene.ObjectType):
    objects = graphene.List(LaikaObjectType)
    pagination = graphene.Field(PaginationResponseType)


class Query(object):
    objects = graphene.List(LaikaObjectType, query=graphene.String(required=False))

    all_object_elements = graphene.Field(
        LaikaObjectElementsIdsType,
        object_id=graphene.String(),
        filter=graphene.JSONString(required=False),
    )
    object = graphene.Field(
        LaikaObjectDataType, id=graphene.String(), object_type=graphene.String()
    )

    objects_paginated = graphene.Field(
        LaikaObjectsResponseType,
        order_by=graphene.Argument(OrderInputType, required=False),
        pagination=graphene.Argument(PaginationInputType, required=False),
        search_criteria=graphene.String(required=False),
    )

    @laika_service(
        permission='objects.view_laikaobject',
        exception_msg='Failed to retrieve object types',
    )
    def resolve_objects(self, info, **kwargs):
        query = json.loads(kwargs.get('query', '{}'))
        if query.get('id') == 'default':
            return [
                LaikaObjectTypeModel.objects.filter(
                    organization=info.context.user.organization
                )
                .order_by('display_name')
                .first()
            ]

        if query.get('id') and not query.get('id').isdigit():
            return [
                LaikaObjectTypeModel.objects.get(
                    organization=info.context.user.organization,
                    type_name=query.get('id'),
                )
            ]

        return LaikaObjectTypeModel.objects.filter(
            organization=info.context.user.organization, **query
        ).order_by('display_name')

    @laika_service(
        permission='objects.view_laikaobject',
        exception_msg='Failed to retrieve all object elements',
    )
    def resolve_all_object_elements(self, info, **kwargs):
        filter_by = kwargs.get('filter', {})
        laika_object = LaikaObjectTypeModel.objects.get(
            organization=info.context.user.organization, id=kwargs.get('object_id', '')
        )
        filter_query = laika_object.get_filter_query(filter_by)
        element_ids = laika_object.elements.filter(filter_query).values_list(
            'id', flat=True
        )

        return LaikaObjectElementsIdsType(ids=element_ids)

    @laika_service(
        permission='objects.view_laikaobject',
        exception_msg='Failed to retrieve object by id',
    )
    def resolve_object(self, info, **kwargs):
        return LaikaObject.objects.filter(
            object_type__organization=info.context.user.organization,
            id=kwargs.get('id'),
            object_type__type_name=kwargs.get('object_type'),
        ).first()

    @laika_service(
        permission='objects.view_laikaobject',
        exception_msg='Failed to retrieve object types',
    )
    def resolve_objects_paginated(self, info, **kwargs):
        objects_qs = LaikaObjectTypeModel.objects.filter(
            organization=info.context.user.organization
        )
        order_by = get_order_by(
            kwargs.get('order_by', {'field': 'display_name', 'order': 'ascend'})
        )

        search_criteria = kwargs.get('search_criteria')
        if search_criteria:
            objects_qs = objects_qs.filter(display_name__icontains=search_criteria)

        paginated_result = get_pagination_result(
            kwargs.get('pagination'), objects_qs.order_by(order_by)
        )

        return LaikaObjectsResponseType(
            objects=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )


class Mutation(graphene.ObjectType):
    create_laika_object = CreateLaikaObject.Field()
    update_laika_object = UpdateLaikaObject.Field()
    bulk_delete_laika_objects = BulkDeleteLaikaObjects.Field()
    bulk_upload_object = BulkUploadObject.Field()

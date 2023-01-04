import os

import graphene

from laika.utils import objects


class FileType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    url = graphene.String()

    def resolve_name(self, info):
        return os.path.basename(self.name)


class InputFileType(graphene.InputObjectType):
    file_name = graphene.String(required=False, default=None)
    file = graphene.String(required=False, default=None)


class ErrorType(graphene.ObjectType):
    '''
    This is deprecated, you should just throw the exception and wrap
    your method with @service_exception to show the user a specific
    error message. That will use the same graphql error specification
    '''

    code = graphene.String()
    message = graphene.String()


class BaseResponseType(graphene.ObjectType):
    '''
    This is deprecated, you should just throw the exception and wrap
    your method with @service_exception to show the user a specific
    error message. That will use the same graphql error specification
    '''

    error = graphene.Field(ErrorType, default_value=None)
    success = graphene.Boolean(default_value=True)


class DjangoInputObjectBaseType(graphene.InputObjectType):
    '''
    Defines a way to turn an input into a model, just create a class that
    specifies an InputMeta attribute like:

    class InputMeta:
        model = <your-django-model-here>

    Then you can update or create new django models based on the input,
    which by defaults copies all the attributes with the same names to
    your model automatically, but you can also provide additional fields
    as kwargs.
    '''

    def to_model(self, update=None, save=True, **kwargs):
        instance = update or self.InputMeta.model(**kwargs)
        objects.copy(self, instance)
        if save:
            instance.save()
        return instance


class OrderInputType(graphene.InputObjectType):
    field = graphene.String(required=True)
    order = graphene.String(required=True)


class PaginationInputType(graphene.InputObjectType):
    page = graphene.Int(required=True)
    page_size = graphene.Int(required=True)


class PaginationResponseType(graphene.ObjectType):
    # TODO: Remove page when kogaio table is removed
    id = graphene.String()
    page = graphene.Int()
    current = graphene.Int()
    pages = graphene.Int()
    has_next = graphene.Boolean()
    has_prev = graphene.Boolean()
    page_size = graphene.Int()
    total = graphene.Int()


class InvalidCellType(graphene.ObjectType):
    required_fields = graphene.List(graphene.String, default_value=[])
    invalid_category = graphene.List(graphene.String, default_value=[])
    invalid_multi_choice = graphene.List(graphene.String, default_value=[])


class BulkUploadErrorType(graphene.ObjectType):
    type = graphene.String()
    addresses = graphene.List(graphene.String, default_value=[])


class BulkUploadType(graphene.ObjectType):
    failed_rows = graphene.List(BulkUploadErrorType, default_value=[])


class UploadResultType(graphene.ObjectType):
    title = graphene.String()
    icon_name = graphene.String()
    icon_color = graphene.String()
    successful_rows = graphene.Int()
    failed_rows = graphene.List(graphene.String, default_value=[])
    ignored_rows = graphene.List(graphene.String, default_value=[])
    invalid_cells = graphene.Field(InvalidCellType, default_value={})
    message = graphene.String()


class FilterItemType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()


class FiltersType(graphene.ObjectType):
    id = graphene.String()
    category = graphene.String()
    items = graphene.List(FilterItemType)


class DataFileType(graphene.ObjectType):
    file_name = graphene.String()
    file = graphene.String()

import graphene

from laika import types


class LaikaObjectInput(graphene.InputObjectType):
    laika_object_type = graphene.Int(required=True)
    laika_object_data = graphene.JSONString(required=True)


class UpdateLaikaObjectInput(graphene.InputObjectType):
    laika_object_id = graphene.Int(required=True)
    laika_object_data = graphene.JSONString(required=True)


class BulkDeleteLaikaObjectsInput(graphene.InputObjectType):
    laika_object_ids = graphene.List(graphene.String, required=True)


class ObjectFileInput(graphene.InputObjectType):
    laika_object_type = graphene.Int(required=True)
    object_file = graphene.Field(types.InputFileType, required=True)


class LaikaObjectFilterType(graphene.InputObjectType):
    field = graphene.String(required=True)
    value = graphene.String()
    operator = graphene.String(required=True)

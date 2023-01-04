from django.db.models import Model


def get_type_from_attribute(model: Model, attr_name: str) -> str:
    return model._meta.get_field(attr_name).get_internal_type()


def is_boolean_field(attr_type: str) -> bool:
    return attr_type == 'BooleanField'


def is_text_field(attr_type: str) -> bool:
    return attr_type == 'TextField'


def is_file_field(attr_type: str) -> bool:
    return attr_type == 'FileField'


def is_datetime_field(attr_type: str) -> bool:
    return attr_type == 'DateTimeField'

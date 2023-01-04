from django.core.exceptions import FieldDoesNotExist
from django.db.models import Model


def copy(source, target, condition=lambda x: x is not None):
    for field_name in dir(source):
        if field_name.startswith('_'):  # Ignore private fields
            continue
        field_value = getattr(source, field_name)
        if hasattr(target, field_name) and condition(field_value):
            setattr(target, field_name, field_value)


def is_valid_model_field(model: Model, field_name: str) -> bool:
    """
    Returns True if the field is valid attribute in the user model.
    Otherwise returns False
    """

    try:
        model._meta.get_field(field_name)
    except FieldDoesNotExist:
        return False
    else:
        return True

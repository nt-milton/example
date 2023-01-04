from django.core.validators import validate_email

from laika.constants import ATTRIBUTES_TYPE

from .base_field import BaseType, InvalidValueErrorType


class EmailFieldType(BaseType):
    OPERATOR_TYPE = ATTRIBUTES_TYPE['USER']

    def validate(self, value):
        required_error = super().validate(value)
        if required_error:
            return required_error
        if value is not None:
            try:
                validate_email(value)
            except Exception:
                return InvalidValueErrorType(
                    field=self.name,
                    description=f'Invalid Email value: {value}',
                    address='',
                )

    def format(self, value, **kwargs):
        return str(value) if value is not None else None

    def get_min_width(self):
        return 200

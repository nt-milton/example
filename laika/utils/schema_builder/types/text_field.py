from laika.constants import ATTRIBUTES_TYPE

from .base_field import BaseType, InvalidValueErrorType


class TextFieldType(BaseType):
    OPERATOR_TYPE = ATTRIBUTES_TYPE['TEXT']

    def validate(self, value):
        required_error = super().validate(value)
        if required_error:
            return required_error
        if value is not None and not isinstance(value, str):
            return InvalidValueErrorType(
                description=f'Invalid String format {value}',
                field=self.name,
                address='',
            )

    def format(self, value, **kwargs):
        return str(value) if value is not None else None

    def get_min_width(self):
        return 200

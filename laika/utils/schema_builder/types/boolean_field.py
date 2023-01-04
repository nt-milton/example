from laika.constants import ATTRIBUTES_TYPE

from .base_field import BaseType, InvalidValueErrorType


class BooleanFieldType(BaseType):
    OPERATOR_TYPE = ATTRIBUTES_TYPE['BOOLEAN']

    def __init__(
        self,
        name,
        required,
        instructions='',
        default_value=None,
        truthy_value='Yes',
        falsy_value='No',
    ):
        super().__init__(name, required, instructions, default_value)
        self.truthy_value = truthy_value
        self.falsy_value = falsy_value

    @property
    def truthy_values(self):
        return [True, 'true', 'TRUE', 'T', 1, 'Yes', 'yes', 'YES', self.truthy_value]

    @property
    def falsy_values(self):
        return [False, 'false', 'FALSE', 'F', 0, 'No', 'no', 'NO', self.falsy_value]

    def validate(self, value):
        required_error = super().validate(value)
        if required_error:
            return required_error
        if (
            value is not None
            and value not in self.falsy_values
            and value not in self.truthy_values
        ):
            return InvalidValueErrorType(
                field=self.name,
                description=f'Invalid Boolean value: {value}',
                address='',
            )

    def format(self, value, **kwargs):
        if value is None:
            return None
        return value in self.truthy_values

    def get_export_header(self):
        return f'{self.name} ({self.truthy_value}/{self.falsy_value})'

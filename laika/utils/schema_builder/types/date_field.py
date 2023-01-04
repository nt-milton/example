import datetime

from laika.constants import ATTRIBUTES_TYPE

from .base_field import BaseType, InvalidValueErrorType


class DateFieldType(BaseType):
    OPERATOR_TYPE = ATTRIBUTES_TYPE['DATE']

    def validate(self, value):
        required_error = super().validate(value)
        if required_error:
            return required_error
        if value is not None and not isinstance(value, datetime.datetime):
            return InvalidValueErrorType(
                field=self.name,
                description=f'Invalid Date value: {value}',
                address='',
            )

    def format(self, value, **kwargs):
        if isinstance(value, datetime.datetime):
            return value.strftime("%Y-%m-%d")

        return None

    def get_min_width(self):
        return 175

    def get_export_header(self):
        return f'{self.name} (MM/DD/YYYY)'

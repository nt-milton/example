import logging

from openpyxl.utils import quote_sheetname

from laika.constants import ATTRIBUTES_TYPE
from laika.utils.spreadsheet import (
    add_list_validation,
    add_range_validation,
    add_validation_legend,
)

from .base_field import BaseType, InvalidValueErrorType

logger = logging.getLogger(__name__)


class SingleSelectField(BaseType):
    OPERATOR_TYPE = ATTRIBUTES_TYPE['TEXT']

    def __init__(
        self, name, required, instructions='', default_value=None, options=None
    ):
        super().__init__(name, required, instructions, default_value)
        self.options = options if options else []

    def validate(self, value):
        required_error = super().validate(value)
        if required_error:
            return required_error

        options = self.options

        if (not options and value is None) or value is None:
            return

        choices = [value.strip() for value in value.split(',')]
        for choice in choices:
            if choice not in options:
                return InvalidValueErrorType(
                    field=self.name,
                    description=f'Invalid Select option: {value}',
                    address='',
                )

    def format_for_filter(self, value, *args, **kwargs):
        options = self.options
        if value is None:
            return []

        if options is None or len(options) == 0:
            logger.warning('Select options cannot be empty')
            return []

        choices = []
        for choice in value.split(','):
            choice_stripped = choice.strip()

            if choice_stripped in options:
                choices.append(choice_stripped)
            else:
                logger.warning(f'"{choice_stripped}" is not a valid option')

        return choices

    def format(self, value, **kwargs):
        options = self.options
        return value if options and value in options else None

    def get_export_header(self):
        return self.name

    def add_validation(self, workbook, sheet, column, title):
        options = self.options
        if not options:
            return
        if len(options) <= 10:
            add_list_validation(options, sheet, column)
            return
        validation_name = f'Validate {title}'
        validation_sheet = workbook.create_sheet(validation_name)
        sheet_name = quote_sheetname(validation_name)

        range_validation = f'{sheet_name}!$A$3:$A${len(options) + 1}'
        add_range_validation(range_validation, sheet, column)
        add_validation_legend(validation_name, options, 1, validation_sheet, 35)

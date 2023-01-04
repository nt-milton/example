import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from laika.utils.query_builder import OPERATORS


@dataclass
class BaseErrorType:
    field: str
    address: str


@dataclass
class RequiredErrorType(BaseErrorType):
    description: str
    type = 'required_value'

    def __post_init__(self):
        if not self.description:
            self.description = 'Required Field'


@dataclass
class InvalidValueErrorType(BaseErrorType):
    description: str
    type = 'invalid_format'


class BaseType(ABC):
    OPERATOR_TYPE = ''
    path = ''

    def __init__(self, name, required, instructions='', default_value=None, path=''):
        self.name = name
        self.required = required
        self.instructions = instructions
        self.default_value = default_value
        self.path = path

    @abstractmethod
    def validate(self, value):
        if self.required and value is None:
            return RequiredErrorType(
                description='Required Field', address='', field=self.name
            )

    @abstractmethod
    def format(self, value):
        pass

    def format_for_filter(self, value, *args, **kwargs):
        """
        Format for incredible filters
        """
        return self.format(value, *args, **kwargs)

    def get_query_filter(self, field, value: str, operator):
        try:
            handler = OPERATORS[self.OPERATOR_TYPE][operator.upper()]
        except Exception:
            raise ValueError(f'Invalid Operator: "{operator}"')
        if handler is None:
            return None

        ctx = {'format_for_filter': True}
        return handler(field, self.format_for_filter(value, **ctx))

    def get_min_width(self):
        return 150

    def get_export_header(self):
        return f'{self.name}'

    def get_export_value(self, value):
        if isinstance(value, dict):
            return json.dumps(value)
        if isinstance(value, list):
            return ', '.join(value)
        return value

    def add_validation(self, workbook, sheet, column, title):
        return None

    def get_default_value(self):
        return self.default_value


@dataclass
class SchemaType:
    sheet_name: str
    header_title: Optional[str]
    fields: List[BaseType]

    @property
    def is_displaying_instructions(self):
        return any(field.instructions != '' for field in self.fields)

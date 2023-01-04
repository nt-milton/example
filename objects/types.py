import datetime
import json
import logging
from abc import ABC, abstractmethod
from enum import Enum

from dateutil.parser import parse
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.db.models.expressions import OrderBy, RawSQL
from openpyxl.worksheet.datavalidation import DataValidation

from laika.utils.query_builder import OPERATORS
from user.models import User

from .constants import ATTRIBUTES_TYPE

logger = logging.getLogger('objects')


class AttributeType(ABC):
    def __init__(self, attribute):
        self.attribute = attribute

    @abstractmethod
    def validate(self):
        pass

    @abstractmethod
    def format(self):
        pass

    def get_filter_query(self, field, value):
        # Add the "data__" prefix to filter data children
        return Q(**{f'data__{field}__icontains': value})

    def get_incredible_filter_query(self, field, value, operator):
        handler = None
        q_filter = None

        try:
            handler = OPERATORS[self.OPERATOR_TYPE][operator.upper()]
        except Exception:
            raise ValueError(f'Invalid Operator: "{operator}"')

        if handler is not None:
            ctx = {'format_for_filter': True}
            q_filter = handler(field, self.format(value, **ctx))
        return q_filter

    def get_order_by(self, order_by):
        """Return the order definition using order_by fields

        RawSQL is required since:
        - field is within a JSONString
        - field could contain whitespaces

        'field' is passed to SQL as parameter to avoid injection
        """
        field = order_by.get('field')
        order = order_by.get('order')
        descending = True if order == "descend" else False

        return OrderBy(RawSQL("data -> %s", (field,)), descending=descending)

    # TODO: Should we remove this? Is only used within the tests
    def get_formatted_value(self, value):
        self.validate(value)
        return self.format(value)

    def get_min_width(self):
        return 150

    def get_export_header(self):
        return f'{self.attribute.name} ({self.attribute.attribute_type.lower()})'

    def get_export_value(self, value):
        if isinstance(value, dict):
            return json.dumps(value)
        if isinstance(value, list):
            return ', '.join(value)
        return value

    def get_data_validation(self):
        return None

    def get_default_value(self):
        return self.attribute.metadata.default_value


class TextAttributeType(AttributeType):
    OPERATOR_TYPE = ATTRIBUTES_TYPE['TEXT']

    def validate(self, value):
        if value is not None and not isinstance(value, str):
            raise ValueError(
                f'Invalid String value "{value}" for attribute "{self.attribute.name}".'
            )

    def format(self, value, **kwargs):
        return str(value) if value is not None else None

    def get_min_width(self):
        return 200


class BooleanAttributeType(AttributeType):
    OPERATOR_TYPE = ATTRIBUTES_TYPE['BOOLEAN']

    def validate(self, value):
        if not isinstance(value, bool):
            raise ValueError(
                f'Invalid Boolean value "{value}"'
                f' for attribute "{self.attribute.name}".'
            )

    def format(self, value, **kwargs):
        return value in [True, 'true', 'True', 't', 'T', 'yes', 'Yes', '1', 1]

    def get_export_header(self):
        return f'{self.attribute.name} (Yes/No)'

    def get_export_value(self, value):
        return 'Yes' if value else None

    def get_data_validation(self):
        return DataValidation(type="list", formula1='"Yes,No"', allow_blank=True)

    def get_default_value(self):
        return self.attribute.metadata.default_value is True


class NumberAttributeType(AttributeType):
    OPERATOR_TYPE = ATTRIBUTES_TYPE['NUMBER']

    def validate(self, value):
        if value is not None and not isinstance(value, (int, float)):
            raise ValueError(
                f'Invalid Number value "{value}" for attribute "{self.attribute.name}".'
            )

    def format(self, value, **kwargs):
        if isinstance(value, (int, float)):
            return value

        if value is None:
            return None

        try:
            return int(value)
        except ValueError:
            pass

        try:
            return float(value)
        except ValueError:
            return None

    def get_data_validation(self):
        return DataValidation(type="decimal")


class DateAttributeType(AttributeType):
    OPERATOR_TYPE = ATTRIBUTES_TYPE['DATE']

    def validate(self, value):
        if value is not None:
            # Raises ValueError if invalid
            parse(value)

    def format(self, value, **kwargs):
        if isinstance(value, datetime.datetime):
            return value.strftime('%Y-%m-%d')

        if isinstance(value, str):
            try:
                return parse(value)
            except ValueError:
                pass

        return None

    def get_min_width(self):
        return 175

    def get_export_header(self):
        return f'{self.attribute.name} (YYYY-MM-DD)'

    def get_data_validation(self):
        return DataValidation(type="date")


class UserAttributeType(AttributeType):
    OPERATOR_TYPE = ATTRIBUTES_TYPE['USER']

    def validate(self, value):
        if value is None:
            return

        if isinstance(value, (str, dict)):
            return

        raise ValueError(
            f'Invalid User "{value}" for attribute "{self.attribute.name}".'
        )

    def format(self, value, **kwargs):
        if not value:
            return None
        try:
            emails = [email.strip() for email in value.split(',')]

            users = User.objects.filter(
                email__in=emails, organization=self.attribute.object_type.organization
            )
            if not users.exists():
                raise ObjectDoesNotExist(f'Email(s): {emails}')

            # To upload specific cell value
            if users.count() == 1:
                return users.first().as_dict()

            # Users that were split from parameter value
            return [user.as_dict() for user in users]
        except ObjectDoesNotExist as e:
            logger.info(
                'User not found for email "%s" in attribute "%s" '
                'and object type id "%s". Error: "%s"',
                value,
                self.attribute.name,
                self.attribute.object_type.id,
                e,
            )
            # To store in the json data the invalid email
            return {'email': value}

    def get_filter_query(self, field, value):
        """For User Type filter by firstName or lastName or email

        Override parent method to include additional filter criteria:
        - firstName
        - lastName
        - email
        """
        query = Q(**{f'data__{field}__firstName__icontains': value})
        query.add(Q(**{f'data__{field}__lastName__icontains': value}), Q.OR)
        query.add(Q(**{f'data__{field}__email__icontains': value}), Q.OR)
        return query

    def get_order_by(self, order_by):
        """For User Type order by firstName and lastName

        Override parent method to include additional order criteria:
        - firstName
        - lastName
        """
        field = order_by.get('field')
        order = order_by.get('order')
        descending = True if order == 'descend' else False

        return OrderBy(
            RawSQL(
                "data -> %s -> 'firstName', data -> %s -> 'lastName'", (field, field)
            ),
            descending=descending,
        )

    def get_min_width(self):
        return 250

    def get_export_header(self):
        return f'{self.attribute.name} (email)'

    def get_export_value(self, value):
        return value['email'] if value else None


class SingleSelectAttributeType(AttributeType):
    OPERATOR_TYPE = ATTRIBUTES_TYPE['SINGLE_SELECT']

    def validate(self, value):
        select_options = self.attribute.metadata.select_options

        if select_options and value is not None:
            choices = [value.strip() for value in value.split(',')]
            for choice in choices:
                if choice not in select_options:
                    raise ValueError(
                        f'Invalid Select option "{value}"'
                        f' for attribute "{self.attribute.name}".'
                    )

    def format(self, value, **kwargs):
        format_for_filter = kwargs.get('format_for_filter', False)
        select_options = self.attribute.metadata.select_options

        if not format_for_filter:
            return value if select_options and value in select_options else None

        if value is None:
            return []

        if select_options is None or len(select_options) == 0:
            logger.warning('Select options cannot be empty')
            return []

        choices = []
        for choice in value.split(','):
            choice_stripped = choice.strip()

            if choice_stripped in select_options:
                choices.append(choice_stripped)
            else:
                logger.warning(f'"{choice_stripped}" is not a valid option')

        return choices

    def get_export_header(self):
        select_options = self.attribute.metadata.select_options
        return (
            self.attribute.name
            if not select_options
            else f'{self.attribute.name} ({",".join(select_options)})'
        )

    def get_data_validation(self):
        select_options = self.attribute.metadata.select_options
        return (
            None
            if not select_options
            else DataValidation(type="list", formula1=f'"{",".join(select_options)}"')
        )


class JSONAttributeType(AttributeType):
    OPERATOR_TYPE = ATTRIBUTES_TYPE['JSON']

    def validate(self, value):
        if value is None:
            return
        try:
            payload = json.loads(value)
            for field in ['template', 'data']:
                if field not in payload:
                    raise ValueError(
                        f'Invalid JSON structure "{value}"'
                        f' for attribute "{self.attribute.name}".'
                        f' field "{field}" not found'
                    )
        except json.JSONDecodeError:
            raise ValueError(
                f'Invalid JSON "{value}" for attribute "{self.attribute.name}".'
            )

    def format(self, value):
        payload = json.loads(value)
        return json.dumps(payload['data'])

    def get_min_width(self):
        return 300


class Types(Enum):
    BOOLEAN = BooleanAttributeType
    NUMBER = NumberAttributeType
    TEXT = TextAttributeType
    DATE = DateAttributeType
    USER = UserAttributeType
    SINGLE_SELECT = SingleSelectAttributeType
    JSON = JSONAttributeType

    @classmethod
    def choices(cls):
        return [(i.name, i.name.replace('_', ' ').title()) for i in cls]


class AttributeTypeFactory:
    @staticmethod
    def get_attribute_type(attribute):
        if attribute.attribute_type in Types.__members__:
            return Types[attribute.attribute_type].value(attribute)

        return Types.TEXT.value(attribute)


def format_users(value: str, attribute, users: dict[str, User]):
    if not value:
        return None
    emails = [email.strip() for email in value.split(',')]
    found_users = [users[email] for email in emails if users.get(email)]

    if not found_users:
        logger.info(
            'User not found for email "%s" in attribute "%s" and object type id "%s".',
            value,
            attribute.name,
            attribute.object_type.id,
        )
        return {'email': value}

    # To upload specific cell value
    if len(found_users) == 1:
        return found_users[0].as_dict()

    # Users that were split from parameter value
    return [user.as_dict() for user in found_users]

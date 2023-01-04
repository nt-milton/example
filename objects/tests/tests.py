from datetime import datetime
from unittest.mock import patch

from django.test import SimpleTestCase

from objects.metadata import DEFAULT_VALUE, IS_PROTECTED, SELECT_OPTIONS, Metadata
from objects.models import Attribute, LaikaObjectType
from objects.types import (
    AttributeTypeFactory,
    BooleanAttributeType,
    DateAttributeType,
    NumberAttributeType,
    SingleSelectAttributeType,
    TextAttributeType,
    Types,
    UserAttributeType,
)

SELECT_OPTIONS_CSV = '"OptionA","OptionB"'
SELECT_OPTIONS_CSV_CONVERTED = ['"OptionA"', '"OptionB"']
SELECT_OPTIONS_ARRAY = ['OptionA', 'OptionB']
INCORRECT_VALUE_NUMBER = 'Incorrect value for Number'


'''
########## Tests for objects.models ##########
'''


# Tests for class Attribute


@patch('django.db.models.Model.save')
def test_single_select_not_changed_on_save(mocked_model_save):
    object_type = LaikaObjectType(id=1)
    attribute = Attribute(
        attribute_type=Types.SINGLE_SELECT.name,
        object_type=object_type,
        _metadata={SELECT_OPTIONS: SELECT_OPTIONS_ARRAY},
    )
    attribute.save()
    assert mocked_model_save.call_count == 1
    assert attribute.attribute_type == Types.SINGLE_SELECT.name


@patch('django.db.models.Model.save')
def test_single_select_to_text_on_save(mocked_model_save):
    object_type = LaikaObjectType(id=1)
    attribute = Attribute(
        attribute_type=Types.SINGLE_SELECT.name, object_type=object_type
    )
    attribute.save()
    assert mocked_model_save.call_count == 1
    assert attribute.attribute_type == Types.TEXT.name


@patch('django.db.models.Model.save')
def test_text_not_changed_on_save(mocked_model_save):
    object_type = LaikaObjectType(id=1)
    attribute = Attribute(attribute_type=Types.TEXT.name, object_type=object_type)
    attribute.save()
    assert mocked_model_save.call_count == 1
    assert attribute.attribute_type == Types.TEXT.name


@patch('django.db.models.Model.save')
def test_default_min_width_on_save(mocked_model_save):
    object_type = LaikaObjectType(id=1)
    attribute = Attribute(attribute_type=Types.BOOLEAN.name, object_type=object_type)
    attribute.save()
    assert mocked_model_save.call_count == 1
    assert attribute.min_width == 150


@patch('django.db.models.Model.save')
def test_text_min_width_on_save(mocked_model_save):
    object_type = LaikaObjectType(id=1)
    attribute = Attribute(attribute_type=Types.TEXT.name, object_type=object_type)
    attribute.save()
    assert mocked_model_save.call_count == 1
    assert attribute.min_width == 200


@patch('django.db.models.Model.save')
def test_existing_min_width_not_changed_on_save(mocked_model_save):
    object_type = LaikaObjectType(id=1)
    attribute = Attribute(
        attribute_type=Types.TEXT.name, object_type=object_type, min_width=500
    )
    attribute.save()
    assert mocked_model_save.call_count == 1
    assert attribute.min_width == 500


'''
########## Tests for objects.metadata ##########
'''


# Tests for empty attributes


def test_no_parameter_for_metadata():
    metadata = Metadata()
    assert metadata.is_protected is False
    assert metadata.default_value is None
    assert metadata.select_options == []


def test_empty_parameter_for_metadata():
    metadata = Metadata({})
    assert metadata.is_protected is False
    assert metadata.default_value is None
    assert metadata.select_options == []


# Tests for attribute is_protected


def test_is_protected_true_bool():
    assert Metadata({IS_PROTECTED: True}).is_protected


def test_is_protected_true_string():
    assert Metadata({IS_PROTECTED: 'True'}).is_protected


def test_is_protected_true_number():
    assert Metadata({IS_PROTECTED: 1}).is_protected


def test_is_protected_false_bool():
    assert Metadata({IS_PROTECTED: False}).is_protected is False


def test_is_protected_false_string():
    assert Metadata({IS_PROTECTED: ''}).is_protected is False


def test_is_protected_false_number():
    assert Metadata({IS_PROTECTED: 0}).is_protected is False


# Tests for attribute default_value


def test_default_value_bool_in_metadata():
    assert Metadata({DEFAULT_VALUE: True}).default_value


def test_default_value_string_in_metadata():
    assert Metadata({DEFAULT_VALUE: 'value'}).default_value == 'value'


# Tests for attribute select_options


def test_select_options_in_metadata():
    metadata = Metadata({SELECT_OPTIONS: SELECT_OPTIONS_ARRAY})
    assert metadata.select_options is SELECT_OPTIONS_ARRAY


# Tests for method to_json


def test_metadata_to_json():
    json = {
        IS_PROTECTED: True,
        DEFAULT_VALUE: 'value',
        SELECT_OPTIONS: SELECT_OPTIONS_ARRAY,
    }
    metadata = Metadata(json)
    assert metadata.to_json() == json


def test_metadata_to_json_select_options_as_csv():
    metadata = Metadata({SELECT_OPTIONS: SELECT_OPTIONS_ARRAY})
    json = metadata.to_json(csv_select_options=True)
    assert json[SELECT_OPTIONS] == SELECT_OPTIONS_CSV


# Tests for method get_csv_select_options


def test_metadata_get_csv_select_options_from_array():
    metadata = Metadata({SELECT_OPTIONS: SELECT_OPTIONS_ARRAY})
    assert metadata.get_csv_select_options() == SELECT_OPTIONS_CSV


def test_get_csv_select_options_is_none_for_empty_metadata():
    metadata = Metadata()
    assert metadata.get_csv_select_options() is None


# Tests for method set_select_options_from_csv


def test_array_after_set_select_options_from_csv():
    metadata = Metadata()
    metadata.set_select_options_from_csv(SELECT_OPTIONS_CSV)
    assert metadata.select_options == SELECT_OPTIONS_CSV_CONVERTED


'''
########## Tests for objects.types ##########
'''


class AttributeTypeFactoryTestCase(SimpleTestCase):
    def test_string_attribute_type(self):
        attribute = Attribute(name='Field', attribute_type=Types.TEXT)
        attribute_type = AttributeTypeFactory.get_attribute_type(attribute)
        self.assertIsInstance(
            attribute_type, TextAttributeType, 'Incorrect Attribute Type for String'
        )
        self.assertEqual(attribute_type.attribute.name, 'Field')

    def test_boolean_attribute_type(self):
        attribute = Attribute(name='Field', attribute_type=Types.BOOLEAN.name)
        attribute_type = AttributeTypeFactory.get_attribute_type(attribute)
        self.assertIsInstance(
            attribute_type, BooleanAttributeType, 'Incorrect Attribute Type for Boolean'
        )
        self.assertEqual(attribute_type.attribute.name, 'Field')

    def test_number_attribute_type(self):
        attribute = Attribute(name='Field', attribute_type=Types.NUMBER.name)
        attribute_type = AttributeTypeFactory.get_attribute_type(attribute)
        self.assertIsInstance(
            attribute_type, NumberAttributeType, 'Incorrect Attribute Type for Number'
        )
        self.assertEqual(attribute_type.attribute.name, 'Field')

    def test_date_attribute_type(self):
        attribute = Attribute(name='Field', attribute_type=Types.DATE.name)
        attribute_type = AttributeTypeFactory.get_attribute_type(attribute)
        self.assertIsInstance(
            attribute_type, DateAttributeType, 'Incorrect Attribute Type for Date'
        )
        self.assertEqual(attribute_type.attribute.name, 'Field')

    def test_user_attribute_type(self):
        attribute = Attribute(name='Field', attribute_type=Types.USER.name)
        attribute_type = AttributeTypeFactory.get_attribute_type(attribute)
        self.assertIsInstance(
            attribute_type, UserAttributeType, 'Incorrect Attribute Type for User'
        )
        self.assertEqual(attribute_type.attribute.name, 'Field')

    def test_single_select_attribute_type(self):
        attribute = Attribute(name='Field', attribute_type=Types.SINGLE_SELECT.name)
        attribute_type = AttributeTypeFactory.get_attribute_type(attribute)
        self.assertIsInstance(
            attribute_type,
            SingleSelectAttributeType,
            'Incorrect Attribute Type for Single Select',
        )
        self.assertEqual(attribute_type.attribute.name, 'Field')

    def test_default_attribute_type(self):
        """Factory returns String Attribute Type for unknown types"""
        attribute = Attribute(name='Field', attribute_type='UNKNOWN')
        attribute_type = AttributeTypeFactory.get_attribute_type(attribute)
        self.assertIsInstance(
            attribute_type,
            TextAttributeType,
            'Incorrect Attribute Type for Unknown Type',
        )
        self.assertEqual(attribute_type.attribute.name, 'Field')


class TextAttributeTypeTestCase(SimpleTestCase):
    def setUp(self):
        self.attribute = Attribute(name='Field', attribute_type=Types.TEXT.name)

    def test_string_correct_attribute_type(self):
        attribute_type = TextAttributeType(self.attribute)
        self.assertEqual(
            attribute_type.get_formatted_value('Hello'),
            'Hello',
            'Incorrect value for String',
        )

    def test_none_correct_attribute_type(self):
        attribute_type = TextAttributeType(self.attribute)
        self.assertEqual(
            attribute_type.get_formatted_value(None), None, 'Incorrect value for String'
        )

    def test_string_incorrect_attribute_type(self):
        attribute_type = TextAttributeType(self.attribute)
        with self.assertRaises(ValueError) as e:
            attribute_type.get_formatted_value(2)
        self.assertEqual(
            e.exception.args[0], 'Invalid String value "2" for attribute "Field".'
        )

    def test_string_format_attribute_type(self):
        attribute_type = TextAttributeType(self.attribute)
        self.assertEqual(attribute_type.format(2), '2')


class BooleanAttributeTypeTestCase(SimpleTestCase):
    def setUp(self):
        self.attribute = Attribute(name='Field', attribute_type=Types.BOOLEAN.name)

    def test_boolean_correct_attribute_type(self):
        attribute_type = BooleanAttributeType(self.attribute)
        self.assertEqual(
            attribute_type.get_formatted_value(True),
            True,
            'Incorrect value for Boolean',
        )

    def test_boolean_incorrect_attribute_type(self):
        attribute_type = BooleanAttributeType(self.attribute)
        with self.assertRaises(ValueError) as e:
            attribute_type.get_formatted_value('True')
        self.assertEqual(
            e.exception.args[0], 'Invalid Boolean value "True" for attribute "Field".'
        )

    def test_boolean_true_format_attribute_type(self):
        self.assert_boolean_format('True', True)

    def test_string_true_format_attribute_type(self):
        self.assert_boolean_format('1', True)

    def test_boolean_false_format_attribute_type(self):
        self.assert_boolean_format('False', False)

    def test_string_false_format_attribute_type(self):
        self.assert_boolean_format('0', False)

    def assert_boolean_format(self, given, expected):
        attribute_type = BooleanAttributeType(self.attribute)
        self.assertEqual(
            attribute_type.format(given), expected, 'Incorrect value for Boolean'
        )


class NumberAttributeTypeTestCase(SimpleTestCase):
    def setUp(self):
        self.attribute = Attribute(name='Field', attribute_type=Types.NUMBER.name)

    def test_number_correct_attribute_type(self):
        attribute_type = NumberAttributeType(self.attribute)
        self.assertEqual(
            attribute_type.get_formatted_value(10), 10, INCORRECT_VALUE_NUMBER
        )

    def test_none_correct_attribute_type(self):
        attribute_type = NumberAttributeType(self.attribute)
        self.assertEqual(
            attribute_type.get_formatted_value(None), None, INCORRECT_VALUE_NUMBER
        )

    def test_number_incorrect_attribute_type(self):
        attribute_type = NumberAttributeType(self.attribute)
        with self.assertRaises(ValueError) as e:
            attribute_type.get_formatted_value('10')
        self.assertEqual(
            e.exception.args[0], 'Invalid Number value "10" for attribute "Field".'
        )

    def test_number_int_format_attribute_type(self):
        self.assert_number_format(10, 10)

    def test_number_float_format_attribute_type(self):
        self.assert_number_format(10.9, 10.9)

    def test_string_int_format_attribute_type(self):
        self.assert_number_format('10', 10)

    def test_string_float_format_attribute_type(self):
        self.assert_number_format('10.9', 10.9)

    def assert_number_format(self, given, expected):
        attribute_type = NumberAttributeType(self.attribute)
        self.assertEqual(attribute_type.format(given), expected, INCORRECT_VALUE_NUMBER)


class DateAttributeTypeTestCase(SimpleTestCase):
    def setUp(self):
        self.attribute = Attribute(name='Field', attribute_type=Types.DATE.name)

    def test_date_correct_attribute_type(self):
        attribute_type = DateAttributeType(self.attribute)
        self.assertEqual(
            type(attribute_type.get_formatted_value('20200102')),
            datetime,
            'Incorrect value for Date',
        )

    def test_none_correct_attribute_type(self):
        attribute_type = DateAttributeType(self.attribute)
        self.assertEqual(
            attribute_type.get_formatted_value(None), None, 'Incorrect value for Date'
        )

    def test_date_incorrect_attribute_type(self):
        attribute_type = DateAttributeType(self.attribute)
        with self.assertRaises(ValueError) as e:
            attribute_type.get_formatted_value('20-20-2020')
        self.assertEqual(e.exception.args[0], 'month must be in 1..12: %s')


class UserAttributeTypeTestCase(SimpleTestCase):
    def setUp(self):
        self.attribute = Attribute(name='Field', attribute_type=Types.USER.name)

    def test_none_correct_attribute_type(self):
        attribute_type = UserAttributeType(self.attribute)
        self.assertEqual(
            attribute_type.get_formatted_value(None), None, 'Incorrect value for User'
        )

    def test_user_incorrect_attribute_type(self):
        attribute_type = UserAttributeType(self.attribute)
        with self.assertRaises(ValueError) as e:
            attribute_type.get_formatted_value(10)
        self.assertEqual(
            e.exception.args[0], 'Invalid User "10" for attribute "Field".'
        )


class SingleSelectAttributeTypeTestCase(SimpleTestCase):
    def setUp(self):
        metadata = {'select_options': ['OptionA', 'OptionB', 'OptionC']}
        self.attribute = Attribute(
            name='Field', attribute_type='SINGLE_SELECT', _metadata=metadata
        )
        self.invalid_value_error_message = 'Incorrect value for Single Select'

    def test_select_correct_attribute_type(self):
        attribute_type = SingleSelectAttributeType(self.attribute)
        self.assertEqual(
            attribute_type.format('OptionA'),
            'OptionA',
            self.invalid_value_error_message,
        )

    def test_select_correct_attribute_type_for_filter(self):
        attribute_type = SingleSelectAttributeType(self.attribute)
        ctx = {'format_for_filter': True}
        self.assertEqual(
            attribute_type.format('OptionA', **ctx),
            ['OptionA'],
            self.invalid_value_error_message,
        )

    def test_select_multiples_correct_attribute_type(self):
        attribute_type = SingleSelectAttributeType(self.attribute)
        ctx = {'format_for_filter': True}
        self.assertEqual(
            attribute_type.format('OptionA, OptionB, OptionC', **ctx),
            ['OptionA', 'OptionB', 'OptionC'],
            self.invalid_value_error_message,
        )

    def test_none_correct_attribute_type(self):
        attribute_type = SingleSelectAttributeType(self.attribute)
        ctx = {'format_for_filter': True}
        self.assertEqual(
            attribute_type.format(None, **ctx), [], self.invalid_value_error_message
        )

    def test_user_incorrect_attribute_type(self):
        attribute_type = SingleSelectAttributeType(self.attribute)
        with self.assertRaises(ValueError) as e:
            attribute_type.get_formatted_value('OptionZ')
        self.assertEqual(
            e.exception.args[0],
            'Invalid Select option "OptionZ" for attribute "Field".',
        )

import pytest

from objects.models import Attribute, LaikaObject, LaikaObjectType
from objects.types import (
    BooleanAttributeType,
    NumberAttributeType,
    SingleSelectAttributeType,
    TextAttributeType,
    Types,
)
from organization.tests import create_organization

IS_VERIFIED_FIELD = 'Is Verified'
STATUS_FIELD = 'Status'
NUMBER_FIELD = 'Number'
KEY_FIELD = 'Key'
OWNER_FIELD = 'Owner'
CREATED_ON_FIELD = 'Created On'
IS_OPERATOR = 'IS'


def create_pull_request_objects(object_type):
    lo_data = [
        {KEY_FIELD: '1001', 'Number': 10, IS_VERIFIED_FIELD: False},
        {KEY_FIELD: '2002', 'Number': 11, IS_VERIFIED_FIELD: True},
        {KEY_FIELD: '2003', 'Number': 12, IS_VERIFIED_FIELD: True},
        {KEY_FIELD: '2004', 'Number': None},
    ]
    for data in lo_data:
        LaikaObject.objects.create(object_type=object_type, data=data)


def create_risk_objects(object_type):
    for status in ['OptionA', 'OptionB', 'OptionC']:
        LaikaObject.objects.create(object_type=object_type, data={STATUS_FIELD: status})


def create_attribute(type_name, metadata={}):
    return Attribute(name='Field', attribute_type=type_name, _metadata=metadata)


def get_attribute_type(AttributeType, type_name, metadata={}):
    attribute = Attribute(name='Field', attribute_type=type_name, _metadata=metadata)
    return AttributeType(attribute)


NUMBER_TYPE = get_attribute_type(NumberAttributeType, type_name=Types.NUMBER.name)
BOOLEAN_TYPE = get_attribute_type(BooleanAttributeType, type_name=Types.BOOLEAN.name)
metadata = {'select_options': ['OptionA', 'OptionB', 'OptionC']}
SINGLE_SELECT_TYPE = get_attribute_type(
    SingleSelectAttributeType, type_name=Types.SINGLE_SELECT.name, metadata=metadata
)
TEXT_TYPE = TextAttributeType(create_attribute(Types.TEXT.name))


@pytest.fixture
def organization():
    return create_organization(name='laika-dev')


@pytest.fixture
def risk_object(organization):
    lo_type = LaikaObjectType.objects.create(
        organization=organization,
        display_name='Risk',
        type_name='risk',
        color='orange',
        icon_name='alarm',
        display_index=12,
    )
    create_risk_objects(lo_type)
    return lo_type


@pytest.fixture
def create_attribute_type(pull_request_object):
    attributes = [
        {'field': KEY_FIELD, 'type': Types.TEXT.name},
        {'field': NUMBER_FIELD, 'type': Types.NUMBER.name},
        {'field': CREATED_ON_FIELD, 'type': Types.DATE.name},
        {'field': OWNER_FIELD, 'type': Types.USER.name},
        {'field': STATUS_FIELD, 'type': Types.SINGLE_SELECT.name},
    ]
    for attr in attributes:
        Attribute.objects.create(
            name=attr['field'],
            attribute_type=attr['type'],
            sort_index=1,
            object_type=pull_request_object,
            _metadata={},
        )


@pytest.fixture
def pull_request_object(organization):
    lo_type = LaikaObjectType.objects.create(
        organization=organization,
        display_name='Pull request',
        type_name='pull_request',
        color='red',
        icon_name='code',
        display_index=10,
    )
    create_pull_request_objects(lo_type)
    return lo_type


@pytest.mark.functional
@pytest.mark.parametrize(
    'input_value, operator ,expected',
    [
        ('100', 'IS', 0),
        ('1001', 'IS', 1),
        ('100', 'CONTAINS', 1),
    ],
)
def test_incredible_filter_text(input_value, operator, expected, pull_request_object):
    query_filter = TEXT_TYPE.get_incredible_filter_query(
        field=f'data__{KEY_FIELD}', value=input_value, operator=operator
    )
    assert pull_request_object.elements.filter(query_filter).count() == expected


@pytest.mark.parametrize(
    'att_type,field,value',
    [
        (NUMBER_TYPE, NUMBER_FIELD, '100'),
        (BOOLEAN_TYPE, IS_VERIFIED_FIELD, 'true'),
        (SINGLE_SELECT_TYPE, STATUS_FIELD, 'true'),
        (TEXT_TYPE, KEY_FIELD, '100'),
    ],
)
def test_invalid_operator(att_type, field, value):
    wrong_operator = 'xx'
    with pytest.raises(ValueError, match=f'Invalid Operator: "{wrong_operator}"'):
        att_type.get_incredible_filter_query(
            field=f'data__{field}', value=value, operator=wrong_operator
        )


@pytest.mark.functional
@pytest.mark.parametrize(
    'operator, input_value,expected',
    [
        ('EQUALS', '10', 1),
        ('EQUALS', 10, 1),
        ('GREATER_THAN_OR_EQUALS_TO', '10', 3),
        ('GREATER_THAN_OR_EQUALS_TO', 11, 2),
        ('LESS_THAN', '10', 0),
        ('LESS_THAN', 11, 1),
        ('LESS_THAN_OR_EQUALS_TO', '10', 1),
        ('LESS_THAN_OR_EQUALS_TO', 11, 2),
        ('GREATER_THAN', '10', 2),
        ('GREATER_THAN', 11, 1),
        ('IS_EMPTY', '', 1),
        ('IS_NOT_EMPTY', '', 3),
    ],
)
def test_number_type(operator, input_value, expected, pull_request_object):
    query_filter = NUMBER_TYPE.get_incredible_filter_query(
        field=f'data__{NUMBER_FIELD}', value=input_value, operator=operator
    )
    assert pull_request_object.elements.filter(query_filter).count() == expected


@pytest.mark.functional
@pytest.mark.parametrize('input_value,expected', [('true', 2), (True, 2), (False, 1)])
def test_boolean_type_is_operator(input_value, expected, pull_request_object):
    query_filter = BOOLEAN_TYPE.get_incredible_filter_query(
        field=f'data__{IS_VERIFIED_FIELD}', value=input_value, operator=IS_OPERATOR
    )
    assert pull_request_object.elements.filter(query_filter).count() == expected


@pytest.mark.functional
@pytest.mark.parametrize(
    'operator,input_value,expected',
    [
        ('IS_ANY_OF', 'OptionA, OptionB', 2),
        ('IS_ANY_OF', 'OptionA', 1),
        ('IS_NONE_OF', 'OptionA, OptionB', 1),
        ('IS_NONE_OF', 'OptionA', 2),
        ('IS', 'OptionA', 1),
    ],
)
def test_single_select_type_is_any_of_operator(
    operator, input_value, expected, risk_object
):
    query_filter = SINGLE_SELECT_TYPE.get_incredible_filter_query(
        field=f'data__{STATUS_FIELD}', value=input_value, operator=operator
    )
    assert risk_object.elements.filter(query_filter).count() == expected


@pytest.mark.functional
@pytest.mark.parametrize(
    'field,value,expected',
    [
        (KEY_FIELD, '11', False),
        (NUMBER_FIELD, '11', True),
        (CREATED_ON_FIELD, '02/19/2021', True),
        (OWNER_FIELD, 'xxx@heylaika.com', False),
        (STATUS_FIELD, 'Resolved', False),
    ],
)
def test_get_annotation(
    field, value, expected, pull_request_object, create_attribute_type
):
    filters = [{'field': field, 'value': value, 'operator': 'IS'}]
    annotate = pull_request_object.get_annotate(filters)

    assert bool(annotate) == expected

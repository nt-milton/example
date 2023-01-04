import pytest

from laika.utils.dictionaries import DictToClass
from laika.utils.exceptions import ServiceException
from laika.utils.schema_builder.template_builder import TemplateBuilder
from laika.utils.schema_builder.types.base_field import SchemaType
from laika.utils.schema_builder.types.boolean_field import BooleanFieldType
from laika.utils.schema_builder.types.single_select_field import SingleSelectField
from laika.utils.schema_builder.types.text_field import TextFieldType

CUSTOM_TITLE = 'My custom title'
CUSTOM_QUESTION = 'My dummy question'


@pytest.fixture
def schema():
    return SchemaType(
        sheet_name='Library',
        header_title='Library',
        fields=[
            TextFieldType(name='Question', required=True),
            SingleSelectField(name='Category', required=True, options=['Yes', 'No']),
            TextFieldType(name='Optional', required=False),
            BooleanFieldType(
                name='Boolean', required=True, truthy_value='True', falsy_value='False'
            ),
        ],
    )


@pytest.fixture
def schema_with_instructions():
    return SchemaType(
        sheet_name='Library',
        header_title='Library',
        fields=[
            TextFieldType(
                name='Question', required=True, instructions='This is an example'
            ),
            SingleSelectField(name='Category', required=True, options=['Yes', 'No']),
            TextFieldType(name='Optional', required=False),
            BooleanFieldType(
                name='Boolean', required=True, truthy_value='True', falsy_value='False'
            ),
        ],
    )


@pytest.fixture
def builder(schema, schema_with_instructions):
    return TemplateBuilder(schemas=[schema, schema_with_instructions])


@pytest.fixture
def valid_workbook_with_instructions(schema_with_instructions):
    def iter_rows(*args, **kwargs):
        return [
            [
                DictToClass({'value': CUSTOM_QUESTION, 'coordinate': 'A3'}),
                DictToClass({'value': 'Yes', 'coordinate': 'B3'}),
                DictToClass({'value': '', 'coordinate': 'C3'}),
                DictToClass({'value': 'True', 'coordinate': 'D3'}),
            ]
        ]

    return DictToClass(
        {schema_with_instructions.sheet_name: DictToClass({'iter_rows': iter_rows})}
    )


@pytest.fixture
def valid_workbook(schema):
    def iter_rows(*args, **kwargs):
        return [
            [
                DictToClass({'value': CUSTOM_QUESTION, 'coordinate': 'A3'}),
                DictToClass({'value': 'Yes', 'coordinate': 'B3'}),
                DictToClass({'value': '', 'coordinate': 'C3'}),
                DictToClass({'value': 'True', 'coordinate': 'D3'}),
            ]
        ]

    return DictToClass({schema.sheet_name: DictToClass({'iter_rows': iter_rows})})


@pytest.fixture
def invalid_workbook(schema):
    def iter_rows(*args, **kwargs):
        return [
            [
                DictToClass({'value': None, 'coordinate': 'A3'}),
                DictToClass({'value': 'Non valid', 'coordinate': 'B3'}),
                DictToClass({'value': None, 'coordinate': 'C3'}),
                DictToClass({'value': '', 'coordinate': 'D3'}),
            ]
        ]

    return DictToClass({schema.sheet_name: DictToClass({'iter_rows': iter_rows})})


def test_build_template_response(builder):
    response = builder.build_response('my filename')
    content_disposition_header = response['Content-Disposition']
    template_filename_header = response['Template-Filename']

    assert content_disposition_header == 'attachment; filename="my filename"'
    assert template_filename_header == 'my filename'


def test_is_valid_excel_for_valid_file(builder):
    builder._is_valid_excel(DictToClass({'file_name': 'test.xlsx'}))
    assert True


def test_is_valid_excel_for_invalid_file(builder):
    with pytest.raises(ServiceException):
        builder._is_valid_excel(DictToClass({'file_name': 'test.pdf'}))
    assert True


def test_validate_headers_should_not_raise_an_error(builder, schema):
    builder._update_start_row()
    result = builder._validate_headers(
        schema,
        {
            2: [
                DictToClass({'value': 'Question'}),
                DictToClass({'value': 'Category'}),
                DictToClass({'value': 'Optional'}),
                DictToClass({'value': 'Boolean (True/False)'}),
            ]
        },
    )
    assert result is None


def test_validate_headers_should_raise_an_error(builder, schema):
    builder._update_start_row()
    error = builder._validate_headers(
        schema,
        {
            2: [
                DictToClass({'value': 'Question'}),
            ]
        },
    )
    assert str(error) == 'Missing header Category'


def test_read_rows_should_parse_valid_workbook_with_instructions(
    builder, schema_with_instructions, valid_workbook_with_instructions
):
    success_rows, _ = builder._read_rows(
        schema_with_instructions, valid_workbook_with_instructions
    )

    assert success_rows[0][schema_with_instructions.fields[0].name] == CUSTOM_QUESTION
    assert success_rows[0][schema_with_instructions.fields[1].name] == 'Yes'
    assert success_rows[0][schema_with_instructions.fields[2].name] == ''
    assert success_rows[0][schema_with_instructions.fields[3].name] is True


def test_read_rows_should_parse_valid_row(builder, schema, valid_workbook):
    success_rows, _ = builder._read_rows(schema, valid_workbook)

    assert success_rows[0][schema.fields[0].name] == CUSTOM_QUESTION
    assert success_rows[0][schema.fields[1].name] == 'Yes'
    assert success_rows[0][schema.fields[2].name] == ''
    assert success_rows[0][schema.fields[3].name] is True


def test_read_rows_should_parse_invalid_row(builder, schema, invalid_workbook):
    _, failed_rows = builder._read_rows(schema, invalid_workbook)

    assert failed_rows[0].field == 'Question'
    assert failed_rows[0].type == 'required_value'
    assert failed_rows[1].field == 'Category'
    assert failed_rows[1].type == 'invalid_format'
    assert failed_rows[2].field == 'Boolean'
    assert failed_rows[2].type == 'invalid_format'

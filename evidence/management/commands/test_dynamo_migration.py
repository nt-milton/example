import pytest

from evidence import constants
from evidence.management.commands.migrate_to_laika_paper import dynamo_to_evidence
from laika.utils.dates import YYYY_MM_DD_HH_MM_SS as DATE_FORMAT

TEST_EMAIL = 'test@heylaika.com'

dynamo_document = {
    'isTemplate': {'BOOL': True},
    'organizationId': {'S': '31f3d57e-c1da-404c-b479-2d350c476fff'},
    'updatedAt': {'N': '1599869372175'},
    'displayId': {'S': 'D-1'},
    'category': {'S': 'Incident Response'},
    'createdAt': {'N': '1599869372175'},
    'owner': {'S': TEST_EMAIL},
    'text': {'M': {'data': {'S': 'Custom data'}, 'type': {'S': 'HTML'}}},
    'description': {
        'S': (
            'This form is to be completed as soon as possible'
            ' following the detection or reporting of an'
            ' Information Technology (IT) security incident.'
            ' This form may be updated and modified if'
            ' necessary.'
        )
    },
    'id': {'S': 'd-04a2f479-b375-401a-a7f3-61556ac634c0'},
    'name': {'S': 'Test'},
}


@pytest.fixture
def sample_document():
    from laika.aws.dynamo import flatten_document

    return flatten_document(dynamo_document)


@pytest.fixture
def empty_document():
    from laika.aws.dynamo import flatten_document

    empty_document = dict(
        dynamo_document, text={'M': {'data': {'NULL': True}, 'type': {'S': 'EMPTY'}}}
    )
    return flatten_document(empty_document)


def test_flatten_dynamo_document():
    from laika.aws.dynamo import flatten_document

    dynamo_response = {
        'isTemplate': {'BOOL': True},
        'updatedAt': {'N': '1599869372175'},
        'owner': {'S': TEST_EMAIL},
        'text': {'M': {'data': {'S': 'value1'}, 'type': {'S': 'HTML'}}},
    }
    expected = {
        'is_template': True,
        'updated_at': '1599869372175',
        'owner': TEST_EMAIL,
        'text': {'data': 'value1', 'type': 'HTML'},
    }
    assert flatten_document(dynamo_response) == expected


def test_name_mapping(sample_document):
    evidence = dynamo_to_evidence(sample_document)
    assert evidence['name'] == 'Test.laikapaper'


def test_description_mapping(sample_document):
    evidence = dynamo_to_evidence(sample_document)
    assert 'Information Technology (IT)' in evidence['description']


def test_updated_at_mapping(sample_document):
    evidence = dynamo_to_evidence(sample_document)
    updated_at = evidence['updated_at'].strftime(DATE_FORMAT)
    assert updated_at == '2020-09-12 00:09:32'


def test_created_at_mapping(sample_document):
    evidence = dynamo_to_evidence(sample_document)
    created_at = evidence['created_at'].strftime(DATE_FORMAT)
    assert created_at == '2020-09-12 00:09:32'


def test_file_name_mapping(sample_document):
    evidence = dynamo_to_evidence(sample_document)
    assert evidence['file'].name == 'Test.laikapaper'


def test_type_mapping(sample_document):
    evidence = dynamo_to_evidence(sample_document)
    assert evidence['type'] == constants.LAIKA_PAPER


def test_file_content_mapping(sample_document):
    evidence = dynamo_to_evidence(sample_document)
    assert evidence['file'].read().decode('utf-8') == 'Custom data'


def test_empty_file_content_mapping(empty_document):
    evidence = dynamo_to_evidence(empty_document)
    assert evidence['file'].read().decode('utf-8') == ''

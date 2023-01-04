import base64
import collections
import tempfile

import pytest
from django.core.files import File

import evidence.constants as constants
from action_item.evidence_handler import (
    add_action_item_documents_or_laika_papers,
    delete_evidence,
    upload_action_item_file,
)
from control.evidence_handler import add_control_documents_or_laika_papers
from control.evidence_handler import delete_evidence as delete_control_evidence
from control.evidence_handler import upload_control_file
from control.tests import create_control
from control.tests.factory import create_action_item
from evidence.constants import FILE
from evidence.models import Evidence
from tag.models import Tag


@pytest.fixture(name="_file_data")
def fixture_create_file_input():
    name = 'test file 1'
    file = base64.b64encode(name.encode())
    file_data = {'file_name': name, 'file': file}
    # namedTuple is to convert a dict into an object
    return [collections.namedtuple("FileObject", file_data.keys())(*file_data.values())]


@pytest.fixture(name="_document_ids")
def fixture_create_document_input(graphql_organization):
    file_name = 'test file 2'
    evidence = Evidence.objects.create(
        name=file_name,
        description='',
        organization=graphql_organization,
        type=FILE,
        file=File(file=tempfile.TemporaryFile(), name=file_name),
    )
    return [evidence.id]


@pytest.fixture(name="_tags")
def fixture_tags(graphql_organization):
    tag_names = [f"tag_{num}" for num in range(4)]
    return [
        Tag.objects.create(name=name, organization=graphql_organization)
        for name in tag_names
    ]


@pytest.fixture(name="_action_item_1")
def fixture_action_item_1():
    return create_action_item(
        name="XX-C-001",
        description="Action item description 1",
        status="new",
        is_required=False,
        is_recurrent=False,
        metadata={'isCustom': True},
    )


@pytest.fixture(name="_action_item_2")
def fixture_action_item_2():
    return create_action_item(
        name="XX-C-002",
        description="Action item description 2",
        status="new",
        is_required=False,
        metadata={'isCustom': True},
    )


@pytest.fixture(name="_control_1")
def fixture_control_1(graphql_organization, _action_item_1, _tags):
    control = create_control(
        organization=graphql_organization,
        display_id=1,
        reference_id="AMG-001",
        name='Control Test 1',
        description='control with tags',
        implementation_notes='',
    )
    control.action_items.add(_action_item_1)
    control.tags.add(*_tags[:2])
    return control


@pytest.fixture(name="_control_2")
def fixture_control_2(graphql_organization, _action_item_2, _tags):
    control = create_control(
        organization=graphql_organization,
        reference_id="AMG-002",
        display_id=2,
        name='Control Test 2',
        description='control with tags',
        implementation_notes='',
    )
    control.action_items.add(_action_item_2)
    control.tags.add(*_tags[1:3])
    return control


@pytest.mark.django_db
def test_add_existing_document_to_action_item(
    graphql_organization, _action_item_1, _document_ids, _control_1
):
    action_item_documents = add_action_item_documents_or_laika_papers(
        graphql_organization, _document_ids, _action_item_1, constants.FILE
    )
    assert action_item_documents == _document_ids
    assert (
        _control_1.tags.first().name
        == Evidence.objects.get(id__in=_document_ids).tags.first().name
    )
    assert (
        _control_1.tags.last().name
        == Evidence.objects.get(id__in=_document_ids).tags.last().name
    )


@pytest.mark.django_db
def test_add_existing_document_to_control(
    graphql_organization, _document_ids, _control_1
):
    control_documents = add_control_documents_or_laika_papers(
        graphql_organization, _document_ids, _control_1, constants.FILE
    )
    assert control_documents == _document_ids
    assert (
        _control_1.tags.first().name
        == Evidence.objects.get(id__in=_document_ids).tags.first().name
    )
    assert (
        _control_1.tags.last().name
        == Evidence.objects.get(id__in=_document_ids).tags.last().name
    )


@pytest.mark.django_db
def test_add_new_file_to_action_item(
    graphql_organization, _action_item_1, _file_data, _control_1
):
    action_item_files = upload_action_item_file(
        graphql_organization, _file_data, _action_item_1
    )
    assert (
        Evidence.objects.get(id__in=action_item_files).name == _file_data[0].file_name
    )
    assert (
        _control_1.tags.first().name
        == Evidence.objects.get(name=_file_data[0].file_name).tags.first().name
    )
    assert (
        _control_1.tags.last().name
        == Evidence.objects.get(name=_file_data[0].file_name).tags.last().name
    )


@pytest.mark.django_db
def test_add_new_file_to_control(graphql_organization, _file_data, _control_1):
    control_files = upload_control_file(graphql_organization, _file_data, _control_1)
    assert Evidence.objects.get(id__in=control_files).name == _file_data[0].file_name
    assert (
        _control_1.tags.first().name
        == Evidence.objects.get(name=_file_data[0].file_name).tags.first().name
    )
    assert (
        _control_1.tags.last().name
        == Evidence.objects.get(name=_file_data[0].file_name).tags.last().name
    )


@pytest.mark.django_db
def test_delete_evidence_from_action_item(
    graphql_organization,
    _action_item_1,
    _action_item_2,
    _document_ids,
    _control_1,
    _control_2,
    _tags,
):
    add_action_item_documents_or_laika_papers(
        graphql_organization, _document_ids, _action_item_1, constants.FILE
    )

    add_action_item_documents_or_laika_papers(
        graphql_organization, _document_ids, _action_item_2, constants.FILE
    )

    evidences = Evidence.objects.filter(id__in=_document_ids)

    assert evidences[0].tags.all().count() == 3

    delete_evidence(_document_ids, _action_item_1, graphql_organization.id)
    evidences = Evidence.objects.filter(id__in=_document_ids)

    assert evidences.count() == 1
    assert evidences[0].tags.all().count() == 2
    assert _tags[0] not in evidences[0].tags.all()
    assert _tags[1] in evidences[0].tags.all()
    assert _tags[2] in evidences[0].tags.all()


@pytest.mark.django_db
def test_delete_evidence_from_control(
    graphql_organization,
    _action_item_1,
    _action_item_2,
    _document_ids,
    _control_1,
    _control_2,
    _tags,
):
    add_control_documents_or_laika_papers(
        graphql_organization, _document_ids, _control_1, constants.FILE
    )

    add_control_documents_or_laika_papers(
        graphql_organization, _document_ids, _control_2, constants.FILE
    )

    evidences = Evidence.objects.filter(id__in=_document_ids)

    assert evidences[0].tags.all().count() == 3

    delete_control_evidence(graphql_organization, _document_ids, _control_1)
    evidences = Evidence.objects.filter(id__in=_document_ids)

    assert evidences.count() == 1
    assert evidences[0].tags.all().count() == 2
    assert _tags[0] not in evidences[0].tags.all()
    assert _tags[1] in evidences[0].tags.all()
    assert _tags[2] in evidences[0].tags.all()

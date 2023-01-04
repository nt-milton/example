import uuid
from unittest.mock import patch

import pytest

from control.models import Control
from evidence.models import Evidence
from laika.aws.dynamo import flatten_document
from organization.models import Organization
from organization.tests import create_organization

from ... import constants
from .migrate_to_laika_paper import Command, migrate_document
from .test_dynamo_migration import dynamo_document


@pytest.fixture
def organization():
    return create_organization(flags=[])


@pytest.mark.django_db
def test_migration_skipped_without_flag():
    create_organization(flags=[])
    command = Command()
    with patch.object(command, '_migrate_organization') as mock:
        command.handle()
        assert mock.called is True
    assert len(Organization.objects.all()) == 1


@pytest.mark.django_db
def test_migration_with_flag(organization):
    command = Command()
    with patch.object(command, '_migrate_organization') as mock:
        command.handle()
        assert mock.called


@pytest.mark.django_db
def test_empty_migration_for_migrated_evidence(organization):
    migrated_evidence = Evidence.objects.create(
        organization=organization,
        type=constants.LAIKA_PAPER,
        legacy_document=uuid.uuid4(),
    )
    document = create_document(migrated_evidence.legacy_document)

    result = migrate_document(organization, document)

    assert result == (None, None, 0, 0, 0, 0)


@pytest.mark.django_db
def test_legacy_evidence_with_existing_laika_paper(organization):
    legacy_evidence = Evidence.objects.create(
        organization=organization,
        type=constants.LAIKA_PAPER,
        legacy_document=uuid.uuid4(),
    )
    document = create_document(legacy_evidence.legacy_document)

    updated_evidence, created, *_ = migrate_document(organization, document)

    assert created is None
    assert updated_evidence is None


@pytest.mark.django_db
def test_legacy_document_to_new_laika_paper(organization):
    new_evidence, created, *_ = migrate_document(organization, create_document())

    assert created
    assert new_evidence.type == constants.LAIKA_PAPER


@pytest.mark.django_db
def test_template_to_laika_paper(organization):
    template_doc = create_document(is_template=True)

    evidence, *_ = migrate_document(organization, template_doc)

    drive_evidence = evidence.drive.first()
    assert drive_evidence.is_template


@pytest.mark.django_db
def test_document_is_not_template_evidence(organization):
    doc = create_document(is_template=False)

    evidence, *_ = migrate_document(organization, doc)

    drive_evidence = evidence.drive.first()
    assert drive_evidence.is_template is False


def create_control_evidence(organization, legacy_evidence):
    control = Control.objects.create(
        organization=organization, name='Test Control', description='Test Description'
    )
    control.evidence.add(legacy_evidence)
    return control


def create_document(id=None, is_template=False):
    if not id:
        id = uuid.uuid4()
    document = flatten_document(dynamo_document)
    document['id'] = f'd-{id}'
    document['is_template'] = is_template
    return document

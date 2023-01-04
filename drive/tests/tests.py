import io
import random
from datetime import datetime

import pytest
from django.core.files import File

from drive import utils
from drive.models import Drive, DriveEvidence, DriveEvidenceData
from evidence.constants import FILE, LAIKA_PAPER
from evidence.evidence_handler import update_file_name_with_timestamp
from evidence.models import Evidence
from laika.utils.dates import YYYY_MM_DD_HH_MM_SS_FF as DATE_TIME_FORMAT
from laika.utils.dates import str_date_to_date_formatted
from laika.utils.strings import find_between
from organization.tests import create_organization
from tag.models import Tag
from training.models import Training
from user.models import Officer, Team, TeamMember
from user.tests import create_user
from vendor.models import OrganizationVendor
from vendor.tests.factory import create_vendor

from .query import GET_LAIKA_LOGS

TIME_ZONE = 'America/New_York'
FILE_NAME = 'File_Name.txt'


@pytest.fixture
def organization():
    organization = create_organization(flags=[])
    return organization


@pytest.fixture
def owner(organization):
    user = create_user(organization=organization, email='new_email@heylaika.com')
    user.first_name = 'Test_First'
    user.last_name = 'Test_Last'
    user.save()
    return user


@pytest.fixture
def file():
    return File(name=FILE_NAME, file=io.BytesIO('This is a test'.encode()))


@pytest.fixture
def all_tags(organization):
    tag = Tag.objects.create(name='Tag', organization=organization)
    system_tag = Tag.objects.create(name='System Tag', organization=organization)
    system_tag_legacy = Tag.objects.create(
        name='System Tag Legacy', organization=organization
    )
    return {
        'tags': [tag],
        'system_tags': [system_tag],
        'system_tags_legacy': [system_tag_legacy],
    }


@pytest.fixture
def team(organization, owner):
    team = Team.objects.create(organization=organization, name='Test_Team')
    TeamMember.objects.create(role='Member', phone='123', user=owner, team=team)
    return team


@pytest.fixture
def officer(organization, owner):
    return Officer.objects.create(
        organization=organization, user=owner, name='Test_Officer'
    )


@pytest.fixture
def training(organization):
    return Training.objects.create(
        organization=organization,
        name='A very important training',
        roles=['OrganizationAdmin'],
        category=['Some category'],
        description='A description',
        slides='',
    )


@pytest.fixture
def vendor(organization):
    vendor = create_vendor(
        name='New Vendor',
        website='www.new-vendor.com',
        description='This is a new vendor',
        is_public=True,
    )
    OrganizationVendor.objects.create(vendor=vendor, organization=organization)
    return vendor


@pytest.fixture
def drive_evidence_documents(organization, file):
    document_numbers = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    random.shuffle(document_numbers)
    for n in range(10):
        current_number = document_numbers[n]
        drive_evidence_data = DriveEvidenceData(FILE, file)
        owner = create_user(organization)
        owner.first_name = f'Laika_{current_number}'
        owner.last_name = f'Space_{current_number}'
        owner.email = f'laika_{current_number}@heylaika.com'
        owner.save()

        drive_evidence = DriveEvidence.objects.custom_create(
            organization=organization,
            owner=owner,
            drive_evidence_data=drive_evidence_data,
        )
        drive_evidence.evidence.name = f'Document #{current_number}'
        drive_evidence.save()


@pytest.fixture
def drive_evidence_document(organization, owner, file):
    drive_evidence_data = DriveEvidenceData(LAIKA_PAPER, file)
    drive_evidence = DriveEvidence.objects.custom_create(
        organization=organization, owner=owner, drive_evidence_data=drive_evidence_data
    )

    return drive_evidence.evidence


#
# Test Custom Create
#


def test_drive_evidence_data_defaults(file):
    drive_evidence_data = DriveEvidenceData(FILE, file)
    assert drive_evidence_data.type == FILE
    assert drive_evidence_data.file is file
    assert drive_evidence_data.is_template is False
    assert drive_evidence_data.tags == []
    assert drive_evidence_data.system_tags == []
    assert drive_evidence_data.system_tags_legacy == []


@pytest.mark.django_db
def test_custom_create_evidence(organization, owner, file):
    drive_evidence_data = DriveEvidenceData(FILE, file)
    drive_evidence = DriveEvidence.objects.custom_create(
        organization=organization, owner=owner, drive_evidence_data=drive_evidence_data
    )
    evidence = drive_evidence.evidence
    assert evidence.type == FILE
    assert evidence.name == FILE_NAME
    assert not evidence.tags.exists()
    assert not evidence.system_tags.exists()
    assert not evidence.system_tags_legacy.exists()
    assert drive_evidence.owner is owner
    assert drive_evidence.drive is organization.drive
    assert drive_evidence.is_template is False


@pytest.mark.django_db
def test_custom_create_evidence_is_template_true(organization, owner, file):
    drive_evidence_data = DriveEvidenceData(FILE, file, is_template=True)
    drive_evidence = DriveEvidence.objects.custom_create(
        organization=organization, owner=owner, drive_evidence_data=drive_evidence_data
    )
    assert drive_evidence.is_template is True


@pytest.mark.django_db
def test_custom_create_evidence_is_template_false(organization, owner, file):
    drive_evidence_data = DriveEvidenceData(FILE, file, is_template=False)
    drive_evidence = DriveEvidence.objects.custom_create(
        organization=organization, owner=owner, drive_evidence_data=drive_evidence_data
    )
    assert drive_evidence.is_template is False


@pytest.mark.django_db
def test_custom_create_evidence_all_tags(organization, owner, file, all_tags):
    tags = all_tags['tags']
    system_tags = all_tags['system_tags']
    system_tags_legacy = all_tags['system_tags_legacy']
    drive_evidence_data = DriveEvidenceData(
        FILE,
        file,
        tags=tags,
        system_tags=system_tags,
        system_tags_legacy=system_tags_legacy,
    )
    drive_evidence = DriveEvidence.objects.custom_create(
        organization=organization, owner=owner, drive_evidence_data=drive_evidence_data
    )
    evidence = drive_evidence.evidence
    assert evidence.type == FILE
    assert evidence.name == FILE_NAME
    assert not evidence.tags.first() is tags[0]
    assert not evidence.system_tags.first() is system_tags[0]
    assert not evidence.system_tags_legacy.first() is system_tags_legacy[0]


@pytest.mark.django_db
def test_custom_create_evidence_existing_name(organization, owner, file):
    drive_evidence_data = DriveEvidenceData(FILE, file)
    drive_evidence = DriveEvidence.objects.custom_create(
        organization=organization, owner=owner, drive_evidence_data=drive_evidence_data
    )
    drive_evidence_duplicate = DriveEvidence.objects.custom_create(
        organization=organization, owner=owner, drive_evidence_data=drive_evidence_data
    )
    evidence = drive_evidence.evidence
    evidence_duplicate = drive_evidence_duplicate.evidence
    assert evidence.type == FILE
    assert evidence.name == FILE_NAME
    assert evidence_duplicate.type == FILE
    assert evidence_duplicate.name == 'File_Name(1).txt'


@pytest.mark.django_db
def test_custom_create_evidence_existing_filter_drive(organization, owner, file):
    new_organization = create_organization(name='New')
    drive_evidence_data = DriveEvidenceData(FILE, file)
    drive_evidence = DriveEvidence.objects.custom_create(
        organization=organization, owner=owner, drive_evidence_data=drive_evidence_data
    )
    # Check existing evidence in another drive, to ensure not repeated
    drive_evidence_duplicate = DriveEvidence.objects.custom_create(
        organization=organization,
        owner=owner,
        drive_evidence_data=drive_evidence_data,
        filters={'drive': new_organization.drive},
    )
    evidence = drive_evidence.evidence
    evidence_duplicate = drive_evidence_duplicate.evidence
    assert evidence.type == FILE
    assert evidence.name == FILE_NAME
    assert evidence_duplicate.type == FILE
    assert evidence_duplicate.name == FILE_NAME


#
# Test Custom Create Teams
#


@pytest.mark.django_db
def test_custom_create_teams(organization, owner, file, team):
    DriveEvidence.objects.custom_create_teams(
        organization=organization,
        time_zone=TIME_ZONE,
        tags={},
        teams=[team.id],
        user=owner,
    )

    evidence = Evidence.objects.get(name__startswith='Test_Team', drive__isnull=False)

    assert not evidence.tags.exists()
    assert not evidence.system_tags.exists()
    assert not evidence.system_tags_legacy.exists()


@pytest.mark.django_db
def test_custom_create_teams_tags(organization, owner, file, team, all_tags):
    tags = all_tags['tags']
    system_tag = all_tags['system_tags']
    system_tag_legacy = all_tags['system_tags_legacy']
    DriveEvidence.objects.custom_create_teams(
        organization=organization,
        time_zone=TIME_ZONE,
        tags=all_tags,
        teams=[team.id],
        user=owner,
    )

    evidence = Evidence.objects.get(name__startswith='Test_Team', drive__isnull=False)

    assert not evidence.tags.first() is tags[0]
    assert not evidence.system_tags.first() is system_tag[0]
    assert not evidence.system_tags_legacy.first() is system_tag_legacy[0]


#
# Test Custom Create Officers
#


@pytest.mark.django_db
def test_custom_create_officers(organization, owner, file, officer):
    DriveEvidence.objects.custom_create_officers(
        organization=organization,
        time_zone=TIME_ZONE,
        tags={},
        officers=[officer.id],
        user=owner,
    )

    evidence = Evidence.objects.get(
        name__startswith='Officers Details_', drive__isnull=False
    )

    assert not evidence.tags.exists()
    assert not evidence.system_tags.exists()
    assert not evidence.system_tags_legacy.exists()


@pytest.mark.django_db
def test_custom_create_officers_tags(organization, owner, file, officer, all_tags):
    tags = all_tags['tags']
    system_tag = all_tags['system_tags']
    system_tag_legacy = all_tags['system_tags_legacy']
    DriveEvidence.objects.custom_create_officers(
        organization=organization,
        time_zone=TIME_ZONE,
        tags=all_tags,
        officers=[officer.id],
        user=owner,
    )

    evidence = Evidence.objects.get(
        name__startswith='Officers Details_', drive__isnull=False
    )

    assert not evidence.tags.first() is tags[0]
    assert not evidence.system_tags.first() is system_tag[0]
    assert not evidence.system_tags_legacy.first() is system_tag_legacy[0]


def test_update_file_name_with_timestamp():
    timestamp = datetime.now()
    file_name = 'Laika Paper test name.laikapaper'

    new_name = update_file_name_with_timestamp(file_name, timestamp)

    date_in_text = find_between(new_name, 'Laika Paper test name_', '.laikapaper')

    assert new_name.startswith('Laika Paper test name_')
    assert new_name.endswith('.laikapaper')

    formatted_date = str_date_to_date_formatted(date_in_text, DATE_TIME_FORMAT)
    assert formatted_date == timestamp


@pytest.mark.django_db
def test_sort_documents(drive_evidence_documents, organization):
    all_drive_evidence = DriveEvidence.objects.filter(drive__organization=organization)
    asc_ordered_drive_evidence = all_drive_evidence.sort(
        {'field': 'owner', 'order': 'ascend'}
    )
    first_evidence = asc_ordered_drive_evidence.first()
    last_evidence = asc_ordered_drive_evidence.last()
    assert first_evidence.owner.first_name == 'Laika_0'
    assert last_evidence.owner.first_name == 'Laika_9'

    desc_ordered_drive_evidence = all_drive_evidence.sort(
        {'field': 'owner', 'order': 'descend'}
    )
    first_evidence = desc_ordered_drive_evidence.first()
    last_evidence = desc_ordered_drive_evidence.last()
    assert first_evidence.owner.first_name == 'Laika_9'
    assert last_evidence.owner.first_name == 'Laika_0'

    ordered_drive_evidence = all_drive_evidence.sort({'field': 'name'})
    first_evidence = ordered_drive_evidence.first()
    last_evidence = ordered_drive_evidence.last()
    assert first_evidence.evidence.name == 'File_Name(1)(1)(1)(1)(1)(1)(1)(1)(1).txt'
    assert last_evidence.evidence.name == FILE_NAME

    ordered_drive_evidence = all_drive_evidence.sort(None)
    first_evidence = ordered_drive_evidence.first()
    last_evidence = ordered_drive_evidence.last()
    assert first_evidence.evidence.name == 'File_Name(1)(1)(1)(1)(1)(1)(1)(1)(1).txt'
    assert last_evidence.evidence.name == FILE_NAME


# This test is being skiped because the sqlite3 version used for testing,
# doesn't support the operations needed in the resolver
@pytest.mark.functional(permissions=['drive.view_driveevidence'])
@pytest.mark.skip()
def test_get_laika_logs(graphql_client, vendor, team, officer, training):
    response = graphql_client.execute(GET_LAIKA_LOGS)
    assert response['data']['laikaLogs']['laikaLogs'].length == 4


@pytest.mark.django_db
def test_document_mapper(drive_evidence_document, organization):
    documents = utils.launchpad_mapper(Drive, organization.id)
    document_context = documents[0]

    assert document_context.name == drive_evidence_document.name
    assert document_context.description == drive_evidence_document.description
    assert document_context.text == drive_evidence_document.evidence_text

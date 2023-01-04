import io
import logging
from abc import ABC

from django.core.files import File

from drive.models import DriveEvidence, DriveEvidenceData
from evidence.constants import LAIKA_PAPER
from laika.utils.html import get_formatted_html
from laika.utils.replace import organization_placeholders, replace_html_template_text
from seeder.seeders.seeder import Seeder
from tag.models import Tag
from user.models import User

logger = logging.getLogger('documents_seeder')

DOCUMENTS_REQUIRED_FIELDS = ['name']

DOCUMENTS_FIELDS = [*DOCUMENTS_REQUIRED_FIELDS, 'description', 'tags', 'owner']


def create_laika_paper(name, text=''):
    return File(
        name=f'{name}.laikapaper',
        file=io.BytesIO(text.encode())
        if text != ''
        else open('drive/assets/empty.laikapaper', 'rb'),
    )


def get_owner(organization, dictionary):
    owner_email = dictionary['owner']
    if not owner_email:
        return None
    owner, _ = User.objects.get_or_create(
        email=owner_email,
        organization=organization,
        defaults={
            'role': '',
            'last_name': '',
            'first_name': '',
            'is_active': False,
            'username': '',
        },
    )
    return owner


def get_row_values(organization, dictionary, status_detail):
    name = dictionary['name']
    owner = get_owner(organization, dictionary)
    tags = (
        [str(tag).strip() for tag in str(dictionary['tags']).split(',')]
        if dictionary['tags']
        else []
    )
    description = dictionary['description'] if dictionary['description'] else ''
    is_template = bool(dictionary.get('is_template', False))
    return name, owner, tags, description, is_template


def replace_placeholders(organization, html_text):
    return replace_html_template_text(
        html_text, organization_placeholders(organization)
    )


def _get_document_file(organization, zip_obj, name):
    try:
        document_file = zip_obj.open(f'documents/{name}.html')
        current_text = document_file.read().decode('utf-8')
        return create_laika_paper(
            name, replace_placeholders(organization, get_formatted_html(current_text))
        )
    except KeyError:
        return create_laika_paper(name)


class Documents(Seeder, ABC):
    def __init__(self, organization, zip_obj, workbook):
        super().__init__()
        logger.info(f'Seeding documents for organization: {organization.id}')
        self._organization = organization
        self._workbook = workbook
        self._zip_obj = zip_obj
        self._sheet_name = 'documents'
        self._fields = DOCUMENTS_FIELDS
        self._required_fields = DOCUMENTS_REQUIRED_FIELDS
        self._required_error_msg = (
            f'Error seeding documents.Fields: {DOCUMENTS_REQUIRED_FIELDS} are required.'
        )
        self._status_detail = []
        self._row_error = False

    def _process_data(self):
        logger.info('Processing documents')
        dictionary = self._dictionary

        name, owner, tags, description, is_template = get_row_values(
            self._organization, dictionary, self._status_detail
        )

        logger.info(
            f'Seeding Laika Paper with name: {name}, '
            f'owner: {owner}, tags: {tags}, '
            f'is_template: {is_template}'
        )

        drive_evidence = DriveEvidence.objects.filter(
            drive=self._organization.drive,
            evidence__name=f'{name}.laikapaper',
            evidence__type=LAIKA_PAPER,
        ).first()
        document_file = _get_document_file(self._organization, self._zip_obj, name)

        if not drive_evidence:
            drive_evidence_data = DriveEvidenceData(
                type=LAIKA_PAPER, file=document_file, is_template=is_template
            )
            drive_evidence = DriveEvidence.objects.custom_create(
                organization=self._organization,
                owner=owner,
                drive_evidence_data=drive_evidence_data,
            )
        else:
            drive_evidence.evidence.file = document_file
            drive_evidence.owner = owner
            drive_evidence.is_template = is_template

        drive_evidence.evidence.description = description
        drive_evidence.evidence.save()
        drive_evidence.save()

        document_file.close()

        for tag in tags:
            t, _ = Tag.objects.get_or_create(organization=self._organization, name=tag)
            drive_evidence.evidence.tags.add(t)

    def _process_exception(self, e):
        name = self._dictionary["name"]
        logger.warning(f'Error seeding document with name: {name} has failed. {e}')
        self._status_detail.append(
            f'Error seeding document with name: {name}. Error: {e}'
        )

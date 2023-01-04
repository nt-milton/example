import io
import logging
from abc import ABC

from django.core.files import File

from laika.utils.html import get_formatted_html
from report.models import Template
from seeder.seeders.seeder import Seeder

logger = logging.getLogger('documents_seeder')

TEMPLATE_FIELDS = ['name']


def _get_template_file(self, name):
    document_file = self._zip_obj.open(f'templates/{name}.html')
    current_text = document_file.read().decode('utf-8')
    formatted_text = get_formatted_html(current_text)
    return File(name=f'{name}.html', file=io.BytesIO(formatted_text.encode()))


class Templates(Seeder, ABC):
    def __init__(self, organization, zip_obj, workbook):
        super().__init__()
        logger.info(f'Seeding templates for organization: {organization.id}')
        self._organization = organization
        self._workbook = workbook
        self._zip_obj = zip_obj
        self._sheet_name = 'templates'
        self._fields = TEMPLATE_FIELDS
        self._required_fields = TEMPLATE_FIELDS
        self._required_error_msg = (
            f'Error seeding templates.Fields: {TEMPLATE_FIELDS} are required.'
        )
        self._status_detail = []
        self._row_error = False

    def _process_data(self):
        template_dic = self._dictionary

        name = template_dic['name']

        logger.info(f'Seeding Template with name: {name}')

        template_file = _get_template_file(self, name)
        Template.objects.create(
            organization=self._organization, name=name, file=template_file
        )

        template_file.close()

    def _process_exception(self, e):
        name = self._dictionary["name"]
        logger.warning(f'Error seeding template with name: {name} has failed. {e}')
        self._status_detail.append(
            f'Error seeding template with name: {name}. Error: {e}'
        )

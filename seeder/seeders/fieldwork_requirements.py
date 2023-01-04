import logging

from fieldwork.models import Requirement
from seeder.constants import REQUIREMENT_FIELDS, REQUIREMENT_REQUIRED_FIELDS
from seeder.seeders.seeder import Seeder

logger = logging.getLogger('fieldwork_seeder')


class FieldworkRequirement(Seeder):
    def __init__(self, audit, workbook):
        logger.info(f'Seeding requirements for audit: {audit.id}')
        self._audit = audit
        self._workbook = workbook
        self._sheet_name = 'requirements'
        self._fields = REQUIREMENT_FIELDS
        self._required_fields = REQUIREMENT_REQUIRED_FIELDS
        self._required_error_msg = (
            'Error seeding audit requirements.'
            'Fields: display-id, name, description'
            'are required.'
        )
        self._status_detail = []
        self._row_error = False

    def _process_data(self):
        dictionary = self._dictionary
        display_id = dictionary['display_id'].strip()

        logger.info(f'Processing audit requirement {display_id}')

        name = dictionary['name'].strip()
        description = dictionary['description'].strip()
        exclude_in_report = dictionary.get('exclude_in_report', False)
        Requirement.objects.update_or_create(
            audit=self._audit,
            display_id=display_id,
            defaults={
                'name': name,
                'description': description,
                'exclude_in_report': exclude_in_report if exclude_in_report else False,
            },
        )

    def _process_exception(self, e):
        display_id = self._dictionary['display_id'].strip()
        logger.exception(f'Requirement: {display_id} has failed.', e)
        self._status_detail.append(
            f'Error seeding audit requirement: {display_id}.Error: {e}'
        )

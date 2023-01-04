import logging

from fieldwork.models import FetchLogic
from seeder.constants import FETCH_LOGIC_FIELDS, FETCH_LOGIC_REQUIRED_FIELDS
from seeder.seeders.seeder import Seeder

logger = logging.getLogger('fieldwork_seeder')


class FieldworkFetchLogic(Seeder):
    def __init__(self, audit, workbook):
        logger.info(f'Seeding fetch logic for audit: {audit.id}')
        self._audit = audit
        self._workbook = workbook
        self._sheet_name = 'fetch_logic'
        self._fields = FETCH_LOGIC_FIELDS
        self._required_fields = FETCH_LOGIC_REQUIRED_FIELDS
        self._required_error_msg = (
            'Error seeding audit fetch logic.'
            f'Fields: {FETCH_LOGIC_REQUIRED_FIELDS} '
            'are required.'
        )
        self._status_detail = []
        self._row_error = False

    def _process_data(self):
        dictionary = self._dictionary
        code = dictionary['code'].strip()

        logger.info(f'Processing audit fetch logic {code}')

        fetch_type = dictionary['type'].strip()
        description = (
            dictionary.get('description', '').strip()
            if dictionary['description']
            else None
        )
        logic = {'query': dictionary['query'].strip()}
        FetchLogic.objects.update_or_create(
            code=code,
            audit=self._audit,
            defaults={'type': fetch_type, 'logic': logic, 'description': description},
        )

    def _process_exception(self, e):
        code = self._dictionary['code'].strip()
        logger.exception(f'Fetch logic: {code} has failed.', e)
        self._status_detail.append(
            f'Error seeding audit fetch logic: {code}.Error: {e}'
        )

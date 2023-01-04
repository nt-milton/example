import logging

from fieldwork.constants import NO_EXCEPTIONS_NOTED, NOT_TESTED, TEST_RESULTS
from fieldwork.models import Requirement, Test
from seeder.constants import FIELDWORK_REQUIRED_TEST_FIELDS, FIELDWORK_TEST_FIELDS
from seeder.seeders.seeder import Seeder

logger = logging.getLogger('fieldwork_seeder')


def are_result_notes_valid(result, notes):
    if result in [NO_EXCEPTIONS_NOTED, NOT_TESTED] and not notes:
        return False

    return True


RESULT_MAPPER = dict((y, x) for x, y in TEST_RESULTS)


class FieldworkTests(Seeder):
    def __init__(self, audit, workbook):
        logger.info(f'Seeding tests for audit: {audit.id}')
        self._audit = audit
        self._workbook = workbook
        self._sheet_name = 'tests'
        self._fields = FIELDWORK_TEST_FIELDS
        self._required_fields = FIELDWORK_REQUIRED_TEST_FIELDS
        self._required_error_msg = (
            'Error seeding audit tests.'
            'Fields: '
            f'{FIELDWORK_REQUIRED_TEST_FIELDS}'
            'are required.'
        )
        self._status_detail = []
        self._row_error = False

    def _process_data(self):
        dictionary = self._dictionary
        display_id = dictionary['display_id'].strip()

        logger.info(f'Processing audit tests {display_id}')

        result = None
        if dictionary.get('result'):
            result = RESULT_MAPPER[dictionary.get('result').strip()]
        notes = dictionary.get('notes')

        if not are_result_notes_valid(result, notes):
            self._status_detail.append(
                f'Failed to seed test {display_id}'
                f', notes cannot be empty for {NO_EXCEPTIONS_NOTED}'
                f' and {NOT_TESTED} results'
            )
            return

        sheet_requirement_id = dictionary['requirement'].strip()
        name = dictionary['name'].strip()
        checklist = dictionary['checklist'].strip()

        requirement = Requirement.objects.get(
            display_id=sheet_requirement_id, audit=self._audit
        )

        test, _ = Test.objects.update_or_create(
            display_id=display_id,
            requirement=requirement,
            defaults={
                'name': name,
                'checklist': checklist,
                'result': result,
                'notes': notes,
            },
        )

    def _process_exception(self, e):
        display_id = self._dictionary['display_id']

        logger.exception(f'Tet: {display_id} has failed.', e)
        self._status_detail.append(f'Error seeding audit test: {display_id}.Error: {e}')

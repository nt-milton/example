import logging

from fieldwork.constants import EVIDENCE_REQUEST_TYPE
from fieldwork.models import Evidence, FetchLogic, Requirement
from seeder.constants import (
    FIELDWORK_EVIDENCE_FIELDS,
    FIELDWORK_REQUIRED_EVIDENCE_FIELDS,
)
from seeder.seeders.seeder import Seeder

logger = logging.getLogger('fieldwork_seeder')


class FieldworkEvidence(Seeder):
    def __init__(self, audit, workbook):
        logger.info(f'Seeding evidence for audit: {audit.id}')
        self._audit = audit
        self._workbook = workbook
        self._sheet_name = 'evidence'
        self._fields = FIELDWORK_EVIDENCE_FIELDS
        self._required_fields = FIELDWORK_REQUIRED_EVIDENCE_FIELDS
        self._required_error_msg = (
            'Error seeding audit evidence.'
            'Fields: '
            f'{FIELDWORK_REQUIRED_EVIDENCE_FIELDS}'
            'are required.'
        )
        self._status_detail = []
        self._row_error = False

    def _process_data(self):
        dictionary = self._dictionary
        display_id = dictionary['display_id'].strip()

        logger.info(f'Processing audit evidence {display_id}')

        sheet_requirement_ids = [
            r.strip() for r in dictionary['requirements'].split(',')
        ]
        name = dictionary['short_name'].strip()
        instructions = dictionary['instructions'].strip()
        fetch_logic_values = dictionary.get('fetch_logic')
        fetch_logic_codes = (
            [r.strip() for r in fetch_logic_values.split(',')]
            if fetch_logic_values
            else ''
        )
        er_type = dictionary['er_type'] or EVIDENCE_REQUEST_TYPE

        evidence, _ = Evidence.objects.update_or_create(
            audit=self._audit,
            display_id=display_id,
            defaults={'name': name, 'instructions': instructions, 'er_type': er_type},
        )

        requirements = Requirement.objects.filter(
            display_id__in=sheet_requirement_ids, audit=self._audit
        )

        evidence.requirements.set(requirements)

        if fetch_logic_codes:
            fetch_logic = FetchLogic.objects.filter(
                code__in=fetch_logic_codes, audit=self._audit
            )
            evidence.fetch_logic.set(fetch_logic)

        if requirements.count() != len(sheet_requirement_ids):
            req_display_ids = [req.display_id for req in requirements]
            for display_id in sheet_requirement_ids:
                if display_id not in req_display_ids:
                    self._status_detail.append(
                        'Unable to link requirement to '
                        f'evidence {evidence.display_id}'
                        'requirement not found: '
                        f' {display_id}'
                    )

    def _process_exception(self, e):
        display_id = self._dictionary['display_id']

        logger.exception(f'Evidence: {display_id} has failed.', e)
        self._status_detail.append(
            f'Error seeding audit evidence: {display_id}.Error: {e}'
        )

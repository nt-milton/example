import json
import logging

from fieldwork.constants import SAMPLE_TYPE
from fieldwork.models import Evidence
from population.models import AuditPopulation
from seeder.constants import POPULATION_FIELDS, POPULATION_REQUIRED_FIELDS
from seeder.seeders.seeder import Seeder

logger = logging.getLogger('fieldwork_seeder')


def validate_json(json_data):
    try:
        return json.loads(json_data)
    except Exception:
        raise TypeError('Invalid Json format')


class Population(Seeder):
    def __init__(self, audit, workbook, zip_obj):
        logger.info(f'Seeding population for audit: {audit.id}')
        self._audit = audit
        self._workbook = workbook
        self._zip_obj = zip_obj
        self._sheet_name = 'populations'
        self._fields = POPULATION_FIELDS
        self._required_fields = POPULATION_REQUIRED_FIELDS
        self._required_error_msg = (
            'Error seeding audit population.'
            'Fields: '
            f'{POPULATION_REQUIRED_FIELDS}'
            'are required.'
        )
        self._status_detail = []
        self._row_error = False

    def _process_data(self):
        dictionary = self._dictionary
        display_id = dictionary['display_id'].strip()

        logger.info(f'Processing audit population {display_id}')

        sheet_er_ids = [r.strip() for r in dictionary['evidence_requests'].split(',')]
        name = dictionary['name'].strip()
        instructions = dictionary['instructions'].strip()
        description = (dictionary['description'] or '').strip()
        default_source = dictionary['default_source'] or ''.strip()
        sample_logic = dictionary['sample_logic'] or ''.strip()
        sample_size = dictionary['sample_size']
        manual_configuration = (
            validate_json(dictionary['manual_configuration'])
            if dictionary['manual_configuration']
            else None
        )
        laika_source_configuration = (
            validate_json(dictionary['laika_source_configuration'])
            if dictionary['laika_source_configuration']
            else None
        )

        population, _ = AuditPopulation.objects.update_or_create(
            audit=self._audit,
            display_id=display_id,
            defaults={
                'name': name,
                'instructions': instructions,
                'description': description,
                'default_source': default_source,
                'sample_logic': sample_logic,
                'sample_size': sample_size,
                'configuration_seed': manual_configuration,
                'laika_source_configuration': laika_source_configuration,
            },
        )

        evidence_requests = Evidence.objects.filter(
            display_id__in=sheet_er_ids, audit=self._audit, er_type=SAMPLE_TYPE
        )

        population.evidence_request.set(evidence_requests)

        if evidence_requests.count() != len(sheet_er_ids):
            er_display_ids = [er.display_id for er in evidence_requests]
            for display_id in sheet_er_ids:
                if display_id not in er_display_ids:
                    self._status_detail.append(
                        'Unable to link evidence request to '
                        f'{population.display_id} '
                        f'evidence request {display_id} not found '
                        'or is not of sample type'
                    )

    def _process_exception(self, e):
        display_id = self._dictionary['display_id']

        logger.exception(
            f'Population: {display_id} has failed. Error: {e}',
        )
        self._status_detail.append(
            f'Error seeding audit population: {display_id}.Error: {e}'
        )

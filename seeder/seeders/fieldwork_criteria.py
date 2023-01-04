import logging

from certification.models import Certification
from fieldwork.models import Criteria, CriteriaAuditType, Requirement
from seeder.constants import (
    FIELDWORK_CRITERIA_FIELDS,
    FIELDWORK_REQUIRED_CRITERIA_FIELDS,
)
from seeder.seeders.seeder import Seeder

logger = logging.getLogger('fieldwork_seeder')


class FieldworkCriteria(Seeder):
    def __init__(self, audit, workbook):
        logger.info(f'Seeding criteria for audit: {audit.id}')
        self._audit = audit
        self._workbook = workbook
        self._sheet_name = 'criteria'
        self._fields = FIELDWORK_CRITERIA_FIELDS
        self._required_fields = FIELDWORK_REQUIRED_CRITERIA_FIELDS
        self._required_error_msg = (
            'Error seeding audit criteria.'
            'Fields: '
            f'{FIELDWORK_REQUIRED_CRITERIA_FIELDS}'
            'are required.'
        )
        self._status_detail = []
        self._row_error = False

    def _process_data(self):
        dictionary = self._dictionary
        display_id = dictionary['display_id'].strip()

        logger.info(f'Processing audit criteria {display_id}')
        description = dictionary['description'].strip()

        criteria, _ = Criteria.objects.update_or_create(
            display_id=display_id,
            audit=self._audit,
            defaults={
                'description': description,
            },
        )

        requirements_reference = dictionary['requirements']
        requirements = None
        if requirements_reference:
            sheet_requirement_ids = [
                r.strip() for r in requirements_reference.split(',')
            ]
            requirements = Requirement.objects.filter(
                display_id__in=sheet_requirement_ids, audit=self._audit
            )

            current_criteria_reqs = criteria.requirements.all()
            criteria.requirements.set(current_criteria_reqs | requirements)

        certification = Certification.objects.filter(
            name__icontains=self._audit.audit_type
        ).first()

        if certification:
            exists_criteria_type = CriteriaAuditType.objects.filter(
                criteria=criteria, type=certification
            ).exists()

            if not exists_criteria_type:
                CriteriaAuditType.objects.create(criteria=criteria, type=certification)

        if requirements and requirements.count() != len(sheet_requirement_ids):
            req_display_ids = [req.display_id for req in requirements]
            for display_id in sheet_requirement_ids:
                if display_id not in req_display_ids:
                    self._status_detail.append(
                        'Unable to link requirement to '
                        f'criteria {criteria.display_id}'
                        'requirement not found: '
                        f' {display_id}'
                    )

    def _process_exception(self, e):
        display_id = self._dictionary['display_id']

        logger.exception(f'Criteria: {display_id} has failed.', e)
        self._status_detail.append(
            f'Error seeding audit criteria: {display_id}.Error: {e}'
        )

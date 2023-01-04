import logging
from multiprocessing.pool import ThreadPool

from django.db import transaction

from program.models import Program
from seeder.seeders.commons import (
    are_columns_empty,
    are_columns_required_empty,
    get_headers,
)
from user.models import User

logger = logging.getLogger('seeder')

PROGRAM_FIELDS_REQUIRED = ['name', 'description']

PROGRAM_FIELDS = [
    'name',
    'description',
    'sort_index',
    'documentation_link',
    'program_lead_email',
    'static_icon',
    'animated_icon',
]

pool = ThreadPool()


def seed(organization, workbook):
    status_detail = []
    if 'programs' not in workbook.sheetnames:
        return status_detail

    programs_sheet = workbook['programs']
    if programs_sheet.cell(row=2, column=1).value is None:
        return status_detail

    headers = get_headers(programs_sheet)
    for row in programs_sheet.iter_rows(min_row=2):
        logger.info('Processing programs sheet')
        dictionary = dict(zip(headers, [c.value for c in row[0 : len(headers)]]))
        if are_columns_empty(dictionary, PROGRAM_FIELDS):
            continue
        try:
            with transaction.atomic():
                if are_columns_required_empty(dictionary, PROGRAM_FIELDS_REQUIRED):
                    status_detail.append(
                        'Error seeding program with name: '
                        f'{dictionary["name"]}. \nRow {row[0].row}.'
                        f'Fields: {PROGRAM_FIELDS_REQUIRED} required.'
                    )
                    continue

                program_lead = None
                if dictionary['program_lead_email']:
                    program_lead, _ = User.objects.get_or_create(
                        email=dictionary['program_lead_email'],
                        organization=organization,
                        defaults={
                            'role': '',
                            'last_name': '',
                            'first_name': '',
                            'is_active': False,
                            'username': '',
                        },
                    )

                Program.objects.update_or_create(
                    organization=organization,
                    name=dictionary['name'].strip(),
                    defaults={
                        'description': dictionary['description'],
                        'sort_index': dictionary['sort_index'],
                        'documentation_link': dictionary['documentation_link'],
                        'program_lead': program_lead,
                        'static_icon': dictionary['static_icon'],
                        'animated_icon': dictionary['animated_icon'],
                    },
                )

        except Exception as e:
            logger.exception(
                f'Program with name: {dictionary["name"]} '
                f'has failed. {e}. \nRow {row[0].row}.'
            )
            status_detail.append(
                f'Error seeding program name: {dictionary["name"]}. \n'
                f'Row: {row[0].row}. Error: {e}'
            )
    return status_detail

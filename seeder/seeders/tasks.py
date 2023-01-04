import logging

from django.db import transaction

from program.constants import GETTING_STARTED_TIER
from program.models import Program, Task
from seeder.seeders.commons import (
    are_columns_empty,
    are_columns_required_empty,
    get_headers,
)

logger = logging.getLogger('seeder')


TASK_REQUIRED_FIELDS = ['program_name', 'name', 'category']

TASK_FIELDS = [
    'program_name',
    'name',
    'category',
    'description',
    'implementation_notes',
    'tier',
    'overview',
]

AMPERSAND = '&'


def seed(organization, workbook):
    status_detail = []
    if 'tasks' not in workbook.sheetnames:
        return status_detail

    tasks_sheet = workbook['tasks']
    if tasks_sheet.cell(row=2, column=1).value is None:
        return status_detail

    headers = get_headers(tasks_sheet)
    for row in tasks_sheet.iter_rows(min_row=2):
        dictionary = dict(zip(headers, [c.value for c in row[0 : len(headers)]]))
        if are_columns_empty(dictionary, TASK_FIELDS):
            continue
        try:
            with transaction.atomic():
                if are_columns_required_empty(dictionary, TASK_REQUIRED_FIELDS):
                    status_detail.append(
                        f'Error seeding task with name: {dictionary["name"]}. '
                        f'Fields:  {TASK_REQUIRED_FIELDS} are required. '
                    )
                    continue

                logger.info(f'Program name related >> {dictionary["program_name"]}')
                program = Program.objects.get(
                    name=dictionary['program_name'].strip(), organization=organization
                )

                identifier_initials = create_task_initials(
                    dictionary['category'].strip()
                )

                Task.objects.update_or_create(
                    program=program,
                    name=dictionary['name'].strip(),
                    defaults={
                        'category': dictionary['category'].strip(),
                        'description': dictionary['description'] or '',
                        'implementation_notes': dictionary['implementation_notes']
                        or '',
                        'tier': dictionary['tier'] or GETTING_STARTED_TIER,
                        'overview': dictionary['overview'] or '',
                        'customer_identifier': identifier_initials
                        + str(create_task_number(identifier_initials, program)),
                        'number': create_task_number(identifier_initials, program),
                    },
                )

        except Exception as e:
            logger.exception(
                f'Task with name: {dictionary["name"]} '
                f'has failed. {e}. \nRow {row[0].row}.'
            )
            status_detail.append(
                f'Error seeding tasks name: {dictionary["name"]}. \n'
                f'Row: {row[0].row}. Error: {e}'
            )
    return status_detail


def create_task_initials(category):
    task_number = ''
    category_tokens = category.replace(AMPERSAND, '').replace('-', ' ').split()

    if len(category_tokens) > 1:
        for token in category_tokens:
            task_number += token[0].upper()
        task_number = task_number[0:2]
    else:
        task_number = category[0:2].upper()

    return task_number


def create_task_number(customer_identifier, program):
    last_number = 1
    provisional_identifier = customer_identifier + str(last_number)

    while len(
        Task.objects.filter(program=program, customer_identifier=provisional_identifier)
    ):
        last_number += 1
        provisional_identifier = customer_identifier + str(last_number)

    return last_number

import logging

from django.db import transaction

from program.models import Program, Task
from seeder.seeders.commons import (
    are_columns_empty,
    are_columns_required_empty,
    get_formatted_headers,
)

logger = logging.getLogger('seeder')

REQUIRED_FIELDS = ['program_name', 'task_name', 'name', 'link', 'type']

FIELDS = [*REQUIRED_FIELDS, 'tags', 'description']

RESOURCE_TYPES = ['podcast', 'article', 'video', 'whitepaper']


def seed(organization, workbook):
    status_detail = []
    if 'how_to_guide' not in workbook.sheetnames:
        return status_detail

    how_to_guide_sheet = workbook['how_to_guide']
    # TODO: Replace with method get_headers from commons
    rows = how_to_guide_sheet.iter_rows(min_row=1, max_row=1)
    first_row = next(rows)
    headings = [c.value for c in first_row]
    headers = get_formatted_headers(headings)

    headers_len = len(headers)
    for row in how_to_guide_sheet.iter_rows(min_row=2):
        how_to_guide_dict = dict(zip(headers, [ht.value for ht in row[0:headers_len]]))

        if are_columns_empty(how_to_guide_dict, FIELDS):
            continue
        try:
            with transaction.atomic():
                name = how_to_guide_dict['name']
                if are_columns_required_empty(how_to_guide_dict, REQUIRED_FIELDS):
                    status_detail.append(
                        'Error seeding how to guide with name: '
                        f'{name}. Fields program_name, task_name,'
                        ' link, type and name are required.'
                    )
                    continue

                resource_type = how_to_guide_dict['type'].strip().lower()

                if resource_type not in RESOURCE_TYPES:
                    status_detail.append(
                        'Error seeding how to guide with name: '
                        f'{name}. Invalid type {resource_type}.'
                    )
                    continue

                logger.info(
                    f'Program name related >> {how_to_guide_dict["program_name"]}'
                )
                program = Program.objects.get(
                    name=how_to_guide_dict['program_name'].strip(),
                    organization=organization,
                )

                logger.info(f'Task name related >> {how_to_guide_dict["task_name"]}')
                task = Task.objects.get(
                    program=program, name=how_to_guide_dict['task_name'].strip()
                )

                task.how_to_guide.append(
                    {
                        'name': how_to_guide_dict['name'],
                        'description': how_to_guide_dict.get('description', ''),
                        'link': how_to_guide_dict['link'],
                        'type': resource_type,
                        'tags': how_to_guide_dict.get('tags', ''),
                    }
                )
                task.save()

        except Exception as e:
            logger.warning(f'How to guide with name: {name} has failed. {e}')
            status_detail.append(
                f'How to guide with name: {name} not saved. Error: {e}'
            )
    return status_detail

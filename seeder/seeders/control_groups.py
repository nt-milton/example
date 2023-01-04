import logging
from datetime import datetime

from control.models import ControlGroup, RoadMap
from control.roadmap.mutations import update_action_items_when_update_control_group
from seeder.seeders.commons import (
    are_columns_empty,
    are_columns_required_empty,
    get_headers,
)

logger = logging.getLogger('seeder_control_groups')
CONTROL_GROUPS = 'control_groups'
REQUIRED_FIELDS = ['reference_id', 'name', 'sort_order']

FIELDS = [*REQUIRED_FIELDS, 'due_date']


def seed(organization, workbook, is_updating=False):
    if CONTROL_GROUPS not in workbook.sheetnames:
        return []

    control_sheet = workbook[CONTROL_GROUPS]

    if control_sheet.cell(row=2, column=1).value is None:
        return []

    status_detail = []
    headers = get_headers(control_sheet)
    for row in control_sheet.iter_rows(min_row=2):
        dictionary = dict(zip(headers, [c.value for c in row[0 : len(headers)]]))

        if row[0:0] is None:
            return []

        if are_columns_empty(dictionary, FIELDS):
            continue

        if are_columns_required_empty(dictionary, REQUIRED_FIELDS):
            status_detail.append(
                'Error seeding control with name: '
                f'{dictionary["reference_id"]},'
                f'Fields: {REQUIRED_FIELDS} required.'
            )
            continue

        try:
            roadmap, _ = RoadMap.objects.get_or_create(organization_id=organization.id)

            group, created = ControlGroup.objects.get_or_create(
                reference_id=dictionary['reference_id'],
                roadmap_id=roadmap.id,
                defaults={
                    'name': dictionary['name'],
                    'due_date': dictionary['due_date'] or None,
                },
            )

            update_group(created, dictionary, group, is_updating)

        except Exception as e:
            logger.exception(
                f'Control Group with name: {dictionary["name"]} '
                f'has failed. {e}. \n Row{row[0].row}'
            )
            status_detail.append(
                'Error seeding control group name '
                f'{dictionary["name"]}. \n'
                f'Row: {row[0].row}. Error: {e}.'
            )

    return status_detail


def log_date_error(date_type):
    msg = f"Error when validating {date_type} format"
    logger.warning(msg)


def seed_dates(group, start_date, due_date):
    validated_start_date = validate_date_format(start_date) if start_date else None
    validated_due_date = validate_date_format(str(due_date)) if due_date else None

    if validated_start_date:
        group.start_date = validated_start_date
    else:
        log_date_error('start date')

    if validated_due_date:
        group.due_date = validated_due_date
    else:
        log_date_error('due date')

    update_action_items_when_update_control_group(
        ControlGroup.objects.filter(pk=group.id),
        validated_start_date,
        validated_due_date,
    )


def update_group(created, dictionary, group, is_updating):
    if created or not is_updating:
        return

    start_date = dictionary.get('start_date')
    due_date = dictionary.get('due_date')

    if due_date or start_date:
        seed_dates(group, start_date, due_date)

    if dictionary.get('name'):
        group.name = dictionary.get('name')

    if dictionary.get('sort_order') and isinstance(dictionary.get('sort_order'), int):
        group.sort_order = dictionary.get('sort_order')

    group.full_clean()
    group.save()


def validate_date_format(date):
    try:
        if '/' in date:
            return datetime.strptime(date, '%m/%d/%Y')
        elif '-' in date:
            return datetime.strptime(date, '%m-%d-%Y')
    except ValueError:
        return False

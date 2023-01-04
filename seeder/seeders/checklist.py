import logging

from django.db import transaction

from action_item.models import ActionItem
from organization.models import OrganizationChecklist
from seeder.seeders.commons import (
    are_columns_empty,
    are_columns_required_empty,
    get_headers,
)
from tag.models import Tag

logger = logging.getLogger(__name__)

CHECKLIST_FIELDS = ['checklist', 'type', 'category', 'description']

CHECKLIST_SHEET_NAME = 'checklist'


def get_or_create_checklist(organization, checklist_name, checklist_type):
    try:
        checklist = OrganizationChecklist.objects.get(
            organization=organization,
            action_item__name__iexact=checklist_name,
            action_item__metadata__type=checklist_type,
        )
    except OrganizationChecklist.DoesNotExist:
        action_item = ActionItem.objects.create(
            name=checklist_name, metadata={'type': checklist_type}
        )
        checklist = OrganizationChecklist.objects.create(
            organization=organization, action_item=action_item
        )
    return checklist


def add_category(checklist, category_name):
    tag, _ = Tag.objects.get_or_create(
        name__exact=category_name,
        organization=checklist.organization,
        defaults={'name': category_name},
    )
    checklist.tags.add(tag)
    return tag


def seed(organization, workbook):
    status_detail = []
    if CHECKLIST_SHEET_NAME not in workbook.sheetnames:
        return status_detail

    checklist_sheet = workbook[CHECKLIST_SHEET_NAME]
    if checklist_sheet.cell(row=2, column=1).value is None:
        return status_detail

    headers = get_headers(checklist_sheet)
    for index, row in enumerate(checklist_sheet.iter_rows(min_row=2), start=1):
        dictionary = dict(zip(headers, [c.value for c in row[0 : len(headers)]]))
        if are_columns_empty(dictionary, CHECKLIST_FIELDS):
            continue
        try:
            with transaction.atomic():
                if are_columns_required_empty(dictionary, CHECKLIST_FIELDS):
                    status_detail.append(
                        'Error seeding checklist step with name:'
                        f'{dictionary["description"]}. '
                        f'Fields:  {CHECKLIST_FIELDS} are required. '
                    )
                    continue
                checklist = get_or_create_checklist(
                    organization, dictionary['checklist'], dictionary['type']
                )
                category = add_category(checklist, dictionary['category'])
                ActionItem.objects.get_or_create(
                    name=f'Step {index}',
                    parent_action_item=checklist.action_item,
                    defaults={
                        'description': dictionary['description'],
                        'metadata': {
                            'isTemplate': True,
                            'category': {'id': category.id, 'name': category.name},
                        },
                    },
                )

        except Exception as e:
            status_detail.append(
                f'Error seeding checklists name: {dictionary["checklist"]}.Error: {e}'
            )
    return status_detail

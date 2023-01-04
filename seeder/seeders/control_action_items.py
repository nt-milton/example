import logging
import re

from action_item.models import ActionItem, ActionItemAssociatedTag, ActionItemStatus
from control.constants import CONTROL_TYPE, MetadataFields
from control.models import Control
from organization.models import Organization
from seeder.seeders.commons import (
    get_formatted_tags,
    get_headers,
    is_valid_workbook,
    validate_if_all_columns_are_empty,
    validate_required_columns,
)
from tag.models import Tag

logger = logging.getLogger('seeder_control_action_items')
CONTROL_ACTION_ITEMS = 'control_action_items'
REQUIRED_FIELDS = ['reference_id', 'control_reference_id', 'name', 'description']

FIELDS = [
    *REQUIRED_FIELDS,
    'requires_evidence',
    'recurrent_schedule',
    'status',
    'tags',
    'sort_order',
]


def seed(organization, workbook, is_updating=False):
    if not is_valid_workbook(workbook, CONTROL_ACTION_ITEMS):
        return []

    status_detail = []
    headers = get_headers(workbook[CONTROL_ACTION_ITEMS])
    for row in workbook[CONTROL_ACTION_ITEMS].iter_rows(min_row=2):
        row_dictionary = dict(zip(headers, [c.value for c in row[0 : len(headers)]]))

        if validate_if_all_columns_are_empty(row_dictionary, FIELDS):
            logger.warning('Columns are empty')
            break

        validation_response = validate_required_columns(row_dictionary, REQUIRED_FIELDS)
        if validation_response:
            status_detail.append(validation_response)
            continue

        if is_updating and not check_controls_existence(organization, row_dictionary):
            continue

        execute_updating(row_dictionary, organization, is_updating, status_detail)

    return status_detail


def execute_updating(
    row_dictionary: dict,
    organization: Organization,
    is_updating: bool,
    status_detail: list[str],
):
    try:
        action_items = ActionItem.objects.filter(
            metadata__referenceId=row_dictionary.get('reference_id'),
            metadata__organizationId=str(organization.id),
        )

        if not action_items:
            create_action_item(
                row_dictionary,
                organization,
                is_updating,
                status_detail,
            )
        else:
            update_action_items(
                row_dictionary,
                organization,
                action_items,
                is_updating,
                status_detail,
            )

    except Exception as e:
        logger.exception(
            f'Control Action Item: {row_dictionary["reference_id"]} has failed. {e}.'
        )
        status_detail.append(
            f'Error seeding control action item: {row_dictionary["reference_id"]}'
        )


def get_requires_evidence(row_dictionary: dict, status_detail: list[str]):
    requires_evidence = row_dictionary.get('requires_evidence') or ''
    if requires_evidence.capitalize() not in ['Yes', 'No', '']:
        requires_evidence = ''
        status_detail.append(
            'Error seeding control action item with name: '
            f'{row_dictionary.get("reference_id")},'
            'requires_evidence is incorrect. Yes, No or empty.'
        )
    return requires_evidence


def update_status(row_dictionary, action_item):
    if (
        row_dictionary.get('status')
        and row_dictionary.get('status') in ActionItemStatus.values
    ):
        action_item.status = row_dictionary.get('status')
        action_item.full_clean()
        action_item.save()


def create_action_item(
    row_dictionary: dict,
    organization: Organization,
    is_updating: bool,
    status_detail: list[str],
):
    requires_evidence = get_requires_evidence(row_dictionary, status_detail)
    recurrent_schedule = row_dictionary.get('recurrent_schedule') or ''
    is_recurrent = False if recurrent_schedule == 'None' else bool(recurrent_schedule)

    action_item = ActionItem.objects.create(
        name=row_dictionary.get('name'),
        description=row_dictionary.get('description'),
        is_required=not is_recurrent,
        is_recurrent=is_recurrent,
        recurrent_schedule=recurrent_schedule,
        display_id=get_sort_order(row_dictionary, status_detail),
        metadata={
            f'{MetadataFields.TYPE.value}': CONTROL_TYPE,
            f'{MetadataFields.ORGANIZATION_ID.value}': str(organization.id),
            f'{MetadataFields.REFERENCE_ID.value}': row_dictionary.get('reference_id'),
            f'{MetadataFields.REQUIRED_EVIDENCE.value}': requires_evidence,
        },
    )

    update_status(row_dictionary, action_item)

    add_action_item_to_control(
        organization, action_item, row_dictionary, status_detail, is_updating
    )
    associate_tags(row_dictionary, organization, action_item)
    return status_detail


def update_action_items(
    row_dictionary: dict,
    organization: Organization,
    action_items,
    is_updating: bool,
    status_detail: list[str],
):
    requires_evidence = get_requires_evidence(row_dictionary, status_detail)
    recurrent_schedule = row_dictionary.get('recurrent_schedule') or ''
    is_recurrent = False if recurrent_schedule == 'None' else bool(recurrent_schedule)

    action_items.update(
        name=row_dictionary.get('name'),
        description=row_dictionary.get('description'),
        is_required=not is_recurrent,
        is_recurrent=is_recurrent,
        recurrent_schedule=recurrent_schedule,
        display_id=get_sort_order(row_dictionary, status_detail),
        metadata={
            f'{MetadataFields.TYPE.value}': CONTROL_TYPE,
            f'{MetadataFields.ORGANIZATION_ID.value}': str(organization.id),
            f'{MetadataFields.REFERENCE_ID.value}': row_dictionary.get('reference_id'),
            f'{MetadataFields.REQUIRED_EVIDENCE.value}': requires_evidence,
        },
    )

    for action_item in action_items:
        update_status(row_dictionary, action_item)

        add_action_item_to_control(
            organization, action_item, row_dictionary, status_detail, is_updating
        )
        associate_tags(row_dictionary, organization, action_item)

    return status_detail


def associate_tags(dictionary, organization, action_item):
    tags_dict = dictionary.get('tags')
    if not tags_dict:
        return

    for tag in get_formatted_tags(tags_dict):
        t, _ = Tag.objects.get_or_create(organization=organization, name=tag)
        ActionItemAssociatedTag.objects.update_or_create(tag=t, action_item=action_item)


def get_formatted_references(cell):
    references = []
    for reference in cell.split(','):
        if reference:
            references.append(re.sub("\n|\r", ' ', reference).strip())
    return references


def add_action_item_to_control(
    organization, action_item, dictionary, status_detail, is_updating
):
    if dictionary.get('control_reference_id'):
        control_reference_ids = get_formatted_references(
            dictionary.get('control_reference_id', '')
        )

        controls = Control.objects.filter(
            reference_id__in=control_reference_ids, organization_id=organization.id
        )

        if not controls:
            status_detail.append(
                'Error seeding action item to control with name: '
                f'{dictionary.get("control_reference_id")}, '
                'controls were not found for this action item. '
            )
            return

        if is_updating:
            action_item.controls.set([])
        for control in controls:
            control.action_items.add(action_item)
            control.has_new_action_items = True
            control.save()


def check_controls_existence(organization, dictionary) -> bool:
    if dictionary.get('control_reference_id'):
        control_reference_ids = get_formatted_references(
            dictionary.get('control_reference_id', '')
        )

        return Control.objects.filter(
            reference_id__in=control_reference_ids, organization_id=organization.id
        ).count()

    return False


def get_sort_order(dictionary, status_detail):
    sort_order = dictionary.get('sort_order')
    if not isinstance(sort_order, int):
        status_detail.append(
            f'Action Item - Sort order value "{sort_order}" is not a number'
        )
        sort_order = 9999999
    return sort_order

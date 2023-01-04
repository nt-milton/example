import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from blueprint.models import ImplementationGuideBlueprint
from certification.models import Certification, UnlockedOrganizationCertification
from control.constants import STATUS
from control.models import Control, ControlGroup, ControlPillar
from control.roadmap.mutations import update_action_items_when_update_control_group
from seeder.seeders.commons import (
    get_headers,
    is_valid_workbook,
    validate_if_all_columns_are_empty,
    validate_required_columns,
)
from user.models import User

logger = logging.getLogger(__name__)


CTRL = 'CTRL'
CONTROLS = 'controls'
CONTROL_REQUIRED_FIELDS = ['reference_id', 'name', 'description']
FRAMEWORK_TAG = 'framework_tag'

CONTROL_FIELDS = [
    *CONTROL_REQUIRED_FIELDS,
    'group_reference_id',
    'status',
    'owner_email',
    'administrator_email',
    'approver_email',
    'frequency',
    'pillar_name',
    'implementation_guide_name',
    'tags',
    'sort_order',
    'framework_tag',
]


def execute_seed(organization, workbook, is_updating=False):
    logger.info('Seeding controls...')
    status_detail = []
    control_objs = []
    display_id = 1

    if not is_valid_workbook(workbook, CONTROLS):
        return []

    headers = get_headers(workbook[CONTROLS])
    for index, row in enumerate(workbook[CONTROLS].iter_rows(min_row=2)):
        dictionary = dict(zip(headers, [c.value for c in row[0 : len(headers)]]))

        if validate_if_all_columns_are_empty(dictionary, CONTROL_FIELDS):
            logger.warning('Columns are empty')
            break

        validation_response = validate_required_columns(
            dictionary, CONTROL_REQUIRED_FIELDS
        )

        if validation_response:
            logger.warning(validation_response)
            status_detail.append(validation_response)
            continue

        try:
            reference_id = str(dictionary.get('reference_id'))
            if CTRL in reference_id:
                control_objs.append(
                    Control(
                        display_id=display_id,
                        organization=organization,
                        reference_id=dictionary.get('reference_id'),
                        name=dictionary.get('name'),
                        owners=get_owners(dictionary),
                        approver=get_approver(dictionary, organization),
                        administrator=get_administrator(dictionary, organization),
                        category='',
                        status=dictionary.get('status')
                        or STATUS.get('NOT IMPLEMENTED'),
                        frequency=dictionary.get('frequency') or 'Not Applicable',
                        description=dictionary.get('description') or '',
                        pillar=get_pillar(dictionary, status_detail),
                        implementation_guide_blueprint=get_implementation_guide(
                            dictionary, status_detail
                        ),
                        framework_tag=get_framework_tag(dictionary),
                    )
                )

                display_id += 1
            else:
                logger.info('Processing new control')
                process_new_control(
                    organization, dictionary, status_detail, is_updating
                )
        except Exception as e:
            logger.exception(
                f'Control with name: {dictionary["name"]} '
                f'has failed. {e}. \n Row{row[0].row}'
            )
            status_detail.append(
                'Error seeding control name '
                f'{dictionary["name"]}. \n'
                f'Row: {row[0].row}. Error: {e}.'
            )
    if len(control_objs):
        with transaction.atomic():
            logger.info('Bulk create controls in DB')
            Control.objects.bulk_create(objs=control_objs)
            logger.info('All controls were inserted')
    return status_detail


def process_new_control(organization, dictionary, status_detail, is_updating):
    control = Control.objects.filter(
        organization_id=organization.id, reference_id=dictionary.get('reference_id')
    ).first()

    if control and is_updating:
        re_seed_control(control, dictionary, status_detail)

    elif not control and is_updating:
        add_new_control_when_seeding_multiple(dictionary, organization, status_detail)

    elif not is_updating:
        create_control_and_link_to_group(organization, dictionary, status_detail)


def re_seed_control(control, dictionary, status_detail):
    control.name = dictionary.get('name')
    control.description = dictionary.get('description') or ''
    control.display_id = get_sort_order(dictionary, status_detail)
    control.framework_tag = dictionary.get(FRAMEWORK_TAG) or ''

    if dictionary.get('status'):
        control.status = dictionary.get('status').upper()

    if dictionary.get('household'):
        control.household = dictionary.get('household')

    pillar = get_pillar(dictionary, status_detail)
    if pillar:
        control.pillar = pillar

    implementation_guide = get_implementation_guide(dictionary, status_detail)

    if implementation_guide:
        control.implementation_guide = implementation_guide

    if dictionary.get('group_reference_id'):
        group = ControlGroup.objects.filter(
            reference_id=dictionary.get('group_reference_id'),
            roadmap__organization_id=control.organization.id,
        ).first()
        if group:
            control.group.set([])
            control.group.add(group)
        if group and group.due_date:
            update_action_items_when_update_control_group([group], group.due_date)

    control.save()


def add_new_control_when_seeding_multiple(dictionary, organization, status_detail):
    unlocked_certs = Certification.objects.filter(
        id__in=UnlockedOrganizationCertification.objects.filter(
            organization_id=organization.id
        ).values_list('certification_id', flat=True)
    )

    for cert in unlocked_certs:
        if dictionary.get(cert.name):
            create_control_and_link_to_group(organization, dictionary, status_detail)


def create_control_and_link_to_group(organization, dictionary, status_detail):
    new_control, created = Control.objects.get_or_create(
        organization=organization,
        reference_id=dictionary.get('reference_id'),
        defaults={
            'name': dictionary.get('name'),
            'household': dictionary.get('household') or '',
            'owners': get_owners(dictionary),
            'approver': get_approver(dictionary, organization),
            'administrator': get_administrator(dictionary, organization),
            'category': '',
            'status': dictionary.get('status') or 'NOT IMPLEMENTED',
            'frequency': dictionary.get('frequency') or 'Not Applicable',
            'description': dictionary.get('description') or '',
            'pillar': get_pillar(dictionary, status_detail),
            'implementation_guide_blueprint': get_implementation_guide(
                dictionary, status_detail
            ),
            'framework_tag': dictionary.get(FRAMEWORK_TAG) or '',
        },
    )

    if created:
        logger.info(f'Control {new_control.reference_id} was created.')
        new_control.display_id = get_sort_order(dictionary, status_detail)
        new_control.save()

    if dictionary.get('group_reference_id'):
        group = ControlGroup.objects.filter(
            reference_id=dictionary.get('group_reference_id'),
            roadmap__organization_id=organization.id,
        ).first()

        if group:
            group.controls.add(new_control)
            group.save()

    return status_detail


def get_administrator(dictionary, organization):
    return get_user(dictionary.get('administrator_email'), organization)


def get_approver(dictionary, organization):
    return get_user(dictionary.get('approver_email'), organization)


def get_user(user_email, organization):
    if not user_email:
        return None

    user, _ = User.objects.get_or_create(
        email=user_email,
        organization=organization,
        defaults={
            'role': '',
            'last_name': '',
            'first_name': '',
            'is_active': False,
            'username': '',
        },
    )

    return user


def get_owners(dictionary):
    owners = []
    if dictionary.get('owner_email'):
        emails = dictionary.get('owner_email').split(',')
        owners = [email.strip() for email in emails]
    return owners


def get_pillar(dictionary, status_detail):
    pillar_name = dictionary.get('pillar_name')
    pillar = None
    if pillar_name:
        try:
            pillar, _ = ControlPillar.objects.get_or_create(
                name=pillar_name, defaults={'description': '', 'illustration': ''}
            )
        except ObjectDoesNotExist:
            status_detail.append(
                f'Pillar "{pillar_name}" not found for control {dictionary.get("name")}'
            )
    return pillar


def get_implementation_guide(dictionary, status_detail):
    implementation_guide_name = dictionary.get('implementation_guide_name')
    implementation_guide = None
    if implementation_guide_name:
        try:
            implementation_guide = ImplementationGuideBlueprint.objects.get(
                name=implementation_guide_name
            )
        except ObjectDoesNotExist:
            status_detail.append(
                f'Implementation Guide "{implementation_guide_name}" '
                f'not found for control {dictionary.get("name")}'
            )
    return implementation_guide


def get_sort_order(dictionary, status_detail):
    sort_order = dictionary.get('sort_order')
    if not isinstance(sort_order, int):
        status_detail.append(
            f'Control - Sort order value "{sort_order}" is not a number'
        )
        sort_order = 9999999
    return sort_order


def get_framework_tag(dictionary):
    return dictionary.get(FRAMEWORK_TAG) or ''

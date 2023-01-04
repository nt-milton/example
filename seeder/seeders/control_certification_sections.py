import copy
import logging

from certification.models import Certification
from control.models import Control, ControlCertificationSection, ControlTag
from seeder.seeders.commons import (
    get_certification_by_name,
    get_certification_section,
    get_certifications_keys,
    get_headers,
    is_valid_workbook,
    map_existing_certifications,
    validate_if_all_columns_are_empty,
)
from seeder.seeders.controls import CONTROL_FIELDS, CONTROLS
from tag.models import Tag

logger = logging.getLogger(__name__)
HOUSEHOLD = 'household'


def get_certifications_names(headers):
    if HOUSEHOLD in headers:
        headers.remove(HOUSEHOLD)

    for cf in CONTROL_FIELDS:
        headers.remove(cf)
    return headers


def get_control_from_list(controls, name, reference_id):
    for c in controls:
        if c.reference_id == reference_id and c.name == name:
            return c


def insert_sections_for_control(control, certification, section_names):
    control_certification_section = []
    if len(section_names) == 0:
        return

    for section in section_names:
        if section:
            cert_section = get_certification_section(section, certification)
            control_certification_section.append(
                ControlCertificationSection(
                    control=control, certification_section=cert_section
                )
            )
    ControlCertificationSection.objects.bulk_create(objs=control_certification_section)


def tag_control(organization_id, control, tags):
    tags_to_update = []
    for t in tags or []:
        tag, _ = Tag.objects.get_or_create(
            name=t.strip(), organization_id=organization_id
        )
        tags_to_update.append(ControlTag(tag=tag, control=control))
    ControlTag.objects.bulk_create(objs=tags_to_update)


def insert_tags_for_control(organization, dictionary, control, is_updating=False):
    logger.info(f'Inserting tags for control {dictionary.get("reference_id")}')

    if not dictionary['tags']:
        return

    if is_updating:
        control.tags.set([])

    tags = str(dictionary['tags']).split(',')
    tag_control(organization.id, control, tags)
    logger.info('Control tags created successfully')


def create_certification_based_on_headers(headers, is_my_compliance=False):
    certification_names = get_certifications_names(copy.copy(headers))
    for cert in certification_names:
        cert_name = map_existing_certifications(cert, is_my_compliance)

        certification, _ = Certification.objects.get_or_create(
            name=cert_name, defaults={'regex': '', 'code': '', 'logo': ''}
        )


def insert_certification_sections(
    dictionary, control, is_updating, is_my_compliance=False
):
    logger.info(f'Inserting sections for control {dictionary.get("reference_id")}')

    certifications_dic = get_certifications_keys(
        dictionary, CONTROL_FIELDS + ['household']
    )

    if is_updating:
        control.certification_sections.set([])
    for key in certifications_dic:
        certification = get_certification_by_name(key, is_my_compliance)
        if certification and certifications_dic[key]:
            section_names = str(certifications_dic[key]).split(',')

            insert_sections_for_control(control, certification, section_names)


def execute_seed(organization, workbook, is_updating=False, is_my_compliance=False):
    logger.info('Seeding certification sections...')
    status_detail = []

    if not is_valid_workbook(workbook, CONTROLS):
        return []

    headers = get_headers(workbook[CONTROLS])
    create_certification_based_on_headers(headers, is_my_compliance)

    for index, row in enumerate(workbook[CONTROLS].iter_rows(min_row=2)):
        dictionary = dict(zip(headers, [c.value for c in row[0 : len(headers)]]))

        if validate_if_all_columns_are_empty(dictionary, CONTROL_FIELDS):
            logger.warning('Columns are empty')
            break

        reference_id = dictionary.get('reference_id')
        try:
            control = Control.objects.filter(
                organization=organization, reference_id=reference_id
            ).first()

            if not control:
                continue

            insert_tags_for_control(organization, dictionary, control, is_updating)

            insert_certification_sections(
                dictionary, control, is_updating, is_my_compliance
            )
        except Exception as e:
            message = (
                'Error seeding certification sections for '
                f'control: {reference_id}.\n'
                f'Row: {index}. Error: {e}. '
            )
            logger.exception(message)
            status_detail.append(message)
    return status_detail

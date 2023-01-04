from certification.models import Certification
from seeder.seeders.commons import (
    are_columns_empty,
    are_columns_required_empty,
    get_certification_section,
    get_headers,
    map_existing_certifications,
)

CERTIFICATION_SECTIONS = 'certification_sections'

CERTIFICATION_SECTIONS_FIELDS = ['name', 'certification_section']


def create_or_get_certification(name: str) -> Certification:
    (certification, _) = Certification.objects.get_or_create(name=name)
    return certification


def seed(workbook, is_my_compliance=False):
    if CERTIFICATION_SECTIONS not in workbook.sheetnames:
        return []

    control_sheet = workbook[CERTIFICATION_SECTIONS]

    if control_sheet.cell(row=2, column=1).value is None:
        return []

    status_detail = []
    headers = get_headers(control_sheet)
    for row in control_sheet.iter_rows(min_row=2):
        dictionary = dict(zip(headers, [c.value for c in row[0 : len(headers)]]))

        if row[0:0] is None:
            return []

        if are_columns_empty(dictionary, CERTIFICATION_SECTIONS_FIELDS):
            continue

        if are_columns_required_empty(dictionary, CERTIFICATION_SECTIONS_FIELDS):
            status_detail.append(
                'Error seeding control section with name: '
                f'{dictionary["name"]},'
                f'Fields: {CERTIFICATION_SECTIONS_FIELDS} required.'
            )
            continue

        certification_name = map_existing_certifications(
            dictionary['name'], is_my_compliance
        )
        certification_section = dictionary['certification_section']
        certification = create_or_get_certification(name=certification_name)

        cert_section_names = certification_section.split(',')
        for cert_section_name in cert_section_names:
            get_certification_section(cert_section_name, certification)

    return status_detail

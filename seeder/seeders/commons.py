import logging
import re

from certification.models import Certification, CertificationSection

SOC_2_TYPE_2 = 'SOC 2 Type 2'
ISO_27001 = 'ISO 27001'
HIPAA = 'HIPAA'
SOC_2_TYPE_1 = 'SOC 2 Type 1'

SEEDER_FILE_FIRST_ROW_TO_READ = 2
SEEDER_FILE_FIRST_COLUMN_TO_READ = 1


logger = logging.getLogger('seeder')


def map_existing_certifications(certification_name, is_my_compliance=False):
    if is_my_compliance:
        return certification_name

    cert_name = certification_name.lower()
    if 'soc 2 type 1' in cert_name:
        return SOC_2_TYPE_1
    if 'soc 2 type 2' in cert_name:
        return SOC_2_TYPE_2
    if 'iso 27002' in cert_name:
        return ISO_27001
    if 'iso 27001' in cert_name:
        return ISO_27001
    if 'us hipaa' in cert_name:
        return HIPAA
    return certification_name


def is_valid_workbook(workbook, sheet_name):
    if sheet_name not in workbook.sheetnames:
        return False

    if (
        workbook[sheet_name]
        .cell(
            row=SEEDER_FILE_FIRST_ROW_TO_READ, column=SEEDER_FILE_FIRST_COLUMN_TO_READ
        )
        .value
        is None
    ):
        return False

    return True


def validate_if_all_columns_are_empty(dictionary, fields) -> bool:
    if are_columns_empty(dictionary, fields):
        return True

    return False


def validate_required_columns(dictionary, fields) -> str:
    if are_columns_required_empty(dictionary, fields):
        return (
            'Error seeding row with reference id: '
            f'{dictionary["reference_id"]},'
            f'Fields: {fields} required. '
        )

    return ''


def get_formatted_headers(headings):
    headers = []
    for header in headings:
        # removes line break and extra blank spaces
        if header:
            header_formatted = re.sub("\n|\r", ' ', header)
            header_formatted = re.sub(" +", ' ', header_formatted)
            headers.append(header_formatted)
    return headers


def are_columns_empty(row, columns):
    return all(not row.get(column) for column in columns)


def are_columns_required_empty(row, columns):
    return any(not row.get(column) for column in columns)


def get_certifications_keys(dictionary, sheet_fields):
    for field in sheet_fields:
        if field in dictionary:
            del dictionary[field]
    return dictionary


def get_certification_section(section_name, certification):
    cert_section = CertificationSection.objects.filter(
        name=section_name.strip(), certification=certification
    ).first()

    if not cert_section:
        cert_section = CertificationSection.objects.create(
            name=section_name.strip(), certification=certification
        )

    return cert_section


def get_certification_by_name(certification_name, is_my_compliance=False):
    try:
        return Certification.objects.get(
            name=map_existing_certifications(certification_name, is_my_compliance)
        )
    except Certification.DoesNotExist:
        logger.exception(
            f'Certification with name {certification_name} does not exist.'
        )
        return None


def should_process_sheet(workbook, sheet_name):
    if sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
        return sheet.cell(row=2, column=1).value or False
    else:
        return False


def get_headers(sheet):
    rows = sheet.iter_rows(min_row=1, max_row=1)
    first_row = next(rows)
    headings = [c.value for c in first_row]
    return get_formatted_headers(headings)


def get_formatted_tags(cell):
    references = []
    separator = "\n|\r"
    for reference in cell.split(','):
        if reference:
            value = re.sub(separator, ' ', reference).strip()
            if value:
                references.append(value)
    return references

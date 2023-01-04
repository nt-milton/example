import logging

from django.core.files import File

from seeder.seeders.commons import (
    are_columns_empty,
    are_columns_required_empty,
    get_certification_by_name,
)

logger = logging.getLogger('seeder')


LOGOS_REQUIRED_FIELDS = ['name']

LOGO_FIELDS = ['name', 'logo']


def seed(zip_obj, workbook, is_my_compliance=False):
    status_detail = []
    if 'certification_logos' not in workbook.sheetnames:
        return status_detail

    cert_logos_sheet = workbook['certification_logos']
    if not cert_logos_sheet.cell(row=2, column=1).value:
        return status_detail

    dictionary = {}
    headers_len = len(LOGO_FIELDS)
    for row in cert_logos_sheet.iter_rows(min_row=2):
        dictionary = dict(zip(LOGO_FIELDS, [c.value for c in row[0:headers_len]]))
        if are_columns_empty(dictionary, LOGO_FIELDS):
            continue
        try:
            if are_columns_required_empty(dictionary, LOGOS_REQUIRED_FIELDS):
                status_detail.append(
                    f'Error seeding vendor with name: {dictionary["name"]}. '
                    f'Fields: {LOGOS_REQUIRED_FIELDS} are required.'
                )
                continue

            if dictionary['logo']:
                with zip_obj.open(
                    f'certification_logos/{dictionary["logo"]}'
                ) as cert_logo:
                    logo = File(name=dictionary['logo'], file=cert_logo)

                    certification = get_certification_by_name(
                        dictionary['name'], is_my_compliance
                    )
                    if certification:
                        certification.logo = logo
                        certification.save()
                    else:
                        status_detail.append(
                            'Error seeding logo for certification name: '
                            f'{dictionary["name"]}. Certification does not '
                            'exist.'
                        )
            else:
                status_detail.append(
                    'Error seeding logo for certification name: '
                    f'{dictionary["name"]}. No logo provided.'
                )

        except Exception as e:
            logger.exception(
                f'Certification with name: {dictionary["name"]} has failed. {e}'
            )
            status_detail.append(
                f'Error seeding certification with name: {dictionary["name"]}.'
                f'Error: {e}'
            )
    return status_detail

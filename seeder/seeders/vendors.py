import logging

from django.core.files import File

from certification.models import Certification
from seeder.seeders.commons import (
    are_columns_empty,
    are_columns_required_empty,
    get_formatted_headers,
    map_existing_certifications,
)
from vendor.models import Vendor, VendorCertification

logger = logging.getLogger('seeder')

VENDOR_FIELDS = ['name', 'website', 'logo', 'description', 'is_public']

VENDOR_REQUIRED_FIELDS = ['name', 'website', 'logo', 'is_public']


def get_certifications_keys(dictionary):
    for vf in VENDOR_FIELDS:
        del dictionary[vf]
    return dictionary


def get_vendor_from_list(name, vendors):
    for v in vendors:
        if v.name == name:
            return v


def get_certification(certification_name, is_my_compliance=False):
    certification = None
    try:
        certification = Certification.objects.get(
            name=map_existing_certifications(certification_name, is_my_compliance)
        )
    except Certification.DoesNotExist:
        logger.exception(
            f'Certification with name {certification_name} does not exist.'
        )
    return certification


def is_global_vendor(row):
    return row.get('is_public', False) is not True


def seed(zip_obj, workbook, is_my_compliance=False):
    status_detail = []
    if 'vendors' not in workbook.sheetnames:
        return status_detail

    vendor_sheet = workbook['vendors']
    if vendor_sheet.cell(row=2, column=1).value is None:
        return status_detail

    # TODO: Replace with method get_headers from commons
    rows = vendor_sheet.iter_rows(min_row=1, max_row=1)
    first_row = next(rows)
    # get the first row
    headings = [c.value for c in first_row]
    headers = get_formatted_headers(headings)
    headers_len = len(headers)
    vendors = []
    for row in vendor_sheet.iter_rows(min_row=2):
        dictionary = dict(zip(headers, [c.value for c in row[0:headers_len]]))
        if are_columns_empty(dictionary, VENDOR_FIELDS):
            continue
        try:
            if are_columns_required_empty(dictionary, VENDOR_REQUIRED_FIELDS):
                status_detail.append(
                    f'Error seeding vendor with name: {dictionary["name"]}. '
                    f'Fields: {VENDOR_REQUIRED_FIELDS} are required.'
                )
                continue

            if is_global_vendor(dictionary):
                status_detail.append(
                    f'Error seeding vendor with name: {dictionary["name"]}. '
                    'Field is_public must be TRUE'
                )
                continue

            if dictionary['logo'].lower() != 'n/a':
                with zip_obj.open(f'vendors/{dictionary["logo"]}') as vendor_logo:
                    logo = File(name=dictionary['logo'], file=vendor_logo)
                    vendor, _ = Vendor.objects.update_or_create(
                        name=dictionary['name'],
                        is_public=dictionary['is_public'],
                        defaults={
                            'website': dictionary['website'],
                            'description': dictionary['description'],
                            'logo': logo,
                        },
                    )
            else:
                vendor, _ = Vendor.objects.update_or_create(
                    name=dictionary['name'],
                    is_public=dictionary['is_public'],
                    defaults={
                        'website': dictionary['website'],
                        'description': dictionary['description'],
                        'logo': None,
                    },
                )
            vendors.append(vendor)

        except Exception as e:
            logger.exception(f'Vendor with name: {dictionary["name"]} has failed. {e}')
            status_detail.append(
                f'Error seeding vendors with name: {dictionary["name"]}.Error: {e}'
            )

    # If relation with certifications come as part of the seeder
    if headers_len > len(VENDOR_FIELDS):
        for row in vendor_sheet.iter_rows(min_row=2):
            dictionary = dict(zip(headers, [c.value for c in row[0:headers_len]]))
            if are_columns_empty(dictionary, VENDOR_FIELDS):
                continue
            try:
                vendor_certifications = []
                vendor = get_vendor_from_list(dictionary['name'], vendors)
                certifications_dic = get_certifications_keys(dictionary)
                for key in certifications_dic:
                    certification = get_certification(key, is_my_compliance)
                    if certifications_dic[key] is not None:
                        if certification is None:
                            status_detail.append(
                                f'Error relating vendor {vendor.name} with '
                                f'certification {key}. Certification does not '
                                'exist.'
                            )
                        else:
                            vendor_certifications.append(
                                VendorCertification(
                                    certification=certification,
                                    vendor=vendor,
                                    url=certifications_dic[key],
                                )
                            )

                VendorCertification.objects.bulk_create(objs=vendor_certifications)

            except Exception as e:
                logger.exception(
                    f'Error adding relations for vendor with name: {vendor.name}. {e}'
                )
                status_detail.append(
                    'Error seeding relations for vendor with name: '
                    f'{dictionary["name"]}.'
                )

    return status_detail

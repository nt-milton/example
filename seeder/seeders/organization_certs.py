import logging
import re

from certification.models import Certification, UnlockedOrganizationCertification
from seeder.seeders.commons import (
    get_certification_by_name,
    map_existing_certifications,
)
from seeder.seeders.seeder import Seeder

logger = logging.getLogger('seeder')

ORGANIZATION_CERT_REQUIRED_FIELD = ['certification_name']
ORGANIZATION_CERT_FIELDS = ['certification_name', 'is_unlocked']


class OrganizationCertification(Seeder):
    def __init__(self, organization, workbook, is_my_compliance=False):
        logger.info(f'Seeding certifications for organization: {organization.id}')
        self._organization = organization
        self._workbook = workbook
        self._sheet_name = 'organization_certifications'
        self._fields = ORGANIZATION_CERT_FIELDS
        self._required_fields = ORGANIZATION_CERT_REQUIRED_FIELD
        self._required_error_msg = (
            'Error seeding certifications. '
            'Fields: '
            f'{ORGANIZATION_CERT_REQUIRED_FIELD} '
            'are required.'
        )
        self._status_detail = []
        self._row_error = False
        self.is_my_compliance = is_my_compliance

    def _process_data(self):
        dictionary = self._dictionary
        organization = self._organization
        is_unlocked = dictionary['is_unlocked']

        certificate = re.sub("\n|\r", ' ', dictionary['certification_name'])
        certificate_name = re.sub(" +", ' ', certificate)

        cert_name = map_existing_certifications(certificate_name, self.is_my_compliance)
        certification, _ = Certification.objects.get_or_create(
            name=cert_name, defaults={'regex': '', 'code': '', 'logo': ''}
        )

        certification = get_certification_by_name(
            certificate_name, self.is_my_compliance
        )
        if certification:
            if is_unlocked:
                UnlockedOrganizationCertification.objects.update_or_create(
                    organization=organization,
                    certification=certification,
                )
            if (
                not is_unlocked
                and UnlockedOrganizationCertification.objects.filter(
                    organization=organization,
                    certification=certification,
                ).exists()
            ):
                UnlockedOrganizationCertification.objects.filter(
                    organization=organization,
                    certification=certification,
                ).delete()

    def _process_exception(self, e):
        logger.exception(
            'Organization Certifications: '
            f'{self._dictionary["certification_name"]} has failed.',
            e,
        )
        self._status_detail.append(
            'Error seeding organization certifications: '
            f'{self._dictionary["certification_name"]}.'
            f'Error: {e}'
        )

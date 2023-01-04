import logging

from policy.models import OnboardingPolicy
from seeder.seeders.seeder import Seeder

logger = logging.getLogger('seeder')

ONBOARDING_POLICY_FIELDS = ['description']


class OnboardingPolicies(Seeder):
    def __init__(self, organization, workbook):
        logger.info(f'Seeding onboarding policies for organization: {organization.id}')
        self._organization = organization
        self._workbook = workbook
        self._sheet_name = 'onboarding_policies'
        self._fields = ONBOARDING_POLICY_FIELDS
        self._required_fields = ONBOARDING_POLICY_FIELDS
        self._required_error_msg = (
            'Error seeding onboarding policy.Field: description is required.'
        )
        self._status_detail = []
        self._row_error = False

    def _process_data(self):
        logger.info('Processing onboarding policy')
        dictionary = self._dictionary

        OnboardingPolicy.objects.update_or_create(
            description=dictionary['description'], organization=self._organization
        )

    def _process_exception(self, e):
        logger.exception(
            f'Onboarding policy: {self._dictionary["description"]} has failed.', e
        )
        self._status_detail.append(
            'Error seeding onboarding policy:'
            f' {self._dictionary["description"]}.'
            f'Error: {e}'
        )

from typing import Union

from audit.sections_factory.sections_factory import (
    Section1,
    Section2,
    Section3,
    Section4,
    SectionsFactory,
)
from audit.sections_factory.utils import get_requirements
from fieldwork.utils import (
    get_sso_cloud_provider,
    get_sso_cloud_providers_quantity,
    get_trust_service_categories,
)
from fieldwork.views import build_criteria_table, get_requirement_description_for_report
from laika.utils.dates import str_date_to_date_formatted

CATEGORY_COPY = 'categories'


def get_common_context(audit):
    organization = audit.organization
    audit_configuration = audit.audit_configuration
    trust_services_categories = audit_configuration['trust_services_categories']
    as_of_date = audit_configuration['as_of_date']
    formatted_as_of_date = str_date_to_date_formatted(as_of_date)

    return {
        'client': organization.name,
        'company_legal_name': organization.legal_name,
        'company_logo': organization.logo.url if organization.logo else None,
        'as_of_date': formatted_as_of_date,
        'TSCs': get_trust_service_categories(trust_services_categories),
        'category_copy': CATEGORY_COPY
        if len(trust_services_categories) > 1
        else 'category',
        'TSC_list': trust_services_categories,
    }


class SOC2Type1Section1(Section1):
    def _generate_context(self):
        audit = self.audit
        common_context = get_common_context(audit)

        criteria = build_criteria_table(audit.id)

        all_criteria = (
            criteria['control_environment']
            + criteria['communication_information']
            + criteria['risk_assessment']
            + criteria['monitoring_activities']
            + criteria['control_activities']
            + criteria['logical_physical_access']
            + criteria['system_operations']
            + criteria['change_management']
            + criteria['risk_mitigation']
            + criteria['additional_criteria_availability']
            + criteria['additional_criteria_confidentiality']
            + criteria['additional_criteria_processing_integrity']
            + criteria['additional_criteria_privacy']
        )

        return {
            'client': common_context['client'],
            'company_legal_name': common_context['company_legal_name'],
            'company_logo': common_context['company_logo'],
            'as_of_date': common_context['as_of_date'],
            'TSCs': common_context['TSCs'],
            'category_copy': common_context['category_copy'],
            'has_criteria': len(all_criteria) > 0,
        }


class SOC2Type1Section2(Section2):
    def _generate_context(self):
        common_context = get_common_context(self.audit)

        return {
            'client': common_context['client'],
            'company_legal_name': common_context['company_legal_name'],
            'as_of_date': common_context['as_of_date'],
            'TSCs': common_context['TSCs'],
        }


class SOC2Type1Section3(Section3):
    def _generate_context(self):
        audit = self.audit
        organization = audit.organization
        common_context = get_common_context(audit)

        return {
            'client': common_context['client'],
            'company_legal_name': common_context['company_legal_name'],
            'as_of_date': common_context['as_of_date'],
            'TSCs': common_context['TSCs'],
            'category_copy': common_context['category_copy'],
            'LCL_5': get_requirement_description_for_report('LCL-5', audit.id),
            'LCL_13': get_requirement_description_for_report('LCL-13', audit.id),
            'LCL_46': get_requirement_description_for_report('LCL-46', audit.id),
            'LCL_20': get_requirement_description_for_report('LCL-20', audit.id),
            'LCL_45': get_requirement_description_for_report('LCL-45', audit.id),
            'TSC_list': common_context['TSC_list'],
            'sso_cloud_provider': get_sso_cloud_provider(organization),
            'sso_cloud_providers_quantity': get_sso_cloud_providers_quantity(
                organization
            ),
        }


class SOC2Type1Section4(Section4):
    def _generate_context(self):
        audit = self.audit
        common_context = get_common_context(audit)
        requirements = get_requirements(audit)

        return {
            **common_context,
            'requirements': requirements,
            'LCL_0': get_requirement_description_for_report('LCL-0', audit.id),
            **build_criteria_table(audit.id),
        }


class SOC2Type1SectionsFactory(SectionsFactory):
    def create_section_1(self) -> Union[dict, None]:
        return SOC2Type1Section1(self.audit).create_section_file()

    def create_section_2(self) -> Union[dict, None]:
        return SOC2Type1Section2(self.audit).create_section_file()

    def create_section_3(self) -> Union[dict, None]:
        return SOC2Type1Section3(self.audit).create_section_file()

    def create_section_4(self) -> Union[dict, None]:
        return SOC2Type1Section4(self.audit).create_section_file()

    def create_section_5(self) -> Union[dict, None]:
        return None

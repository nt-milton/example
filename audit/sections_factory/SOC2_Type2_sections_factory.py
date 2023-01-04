from typing import Union

from audit.constants import SECTION_5
from audit.sections_factory.sections_factory import (
    Section1,
    Section2,
    Section3,
    Section4,
    Section5,
    SectionsFactory,
)
from audit.sections_factory.utils import get_requirements
from auditor.utils import (
    get_criteria_by_audit_id,
    get_requirement_tests,
    get_requirements_by_args,
)
from fieldwork.models import Criteria, CriteriaRequirement, Requirement
from fieldwork.utils import (
    build_criteria_table,
    get_sso_cloud_provider,
    get_sso_cloud_providers_quantity,
    get_trust_service_categories,
)
from fieldwork.views import get_requirement_description_for_report
from laika.utils.dates import MMMM_DD_YYYY, str_date_to_date_formatted

SYSTEM_NAME = '{system_name}'


class SOC2Type2Section1(Section1):
    def _generate_context(self):
        audit = self.audit
        organization = audit.organization
        audit_configuration = audit.audit_configuration

        start_period_unformatted, end_period_unformatted = audit_configuration[
            'as_of_date'
        ].split(',')
        start_period = str_date_to_date_formatted(start_period_unformatted).strftime(
            MMMM_DD_YYYY
        )
        end_period = str_date_to_date_formatted(end_period_unformatted).strftime(
            MMMM_DD_YYYY
        )
        review_period = f'{start_period} to {end_period}'
        not_tested_criteria_requirements = CriteriaRequirement.objects.filter(
            criteria__audit_id=audit.id,
            requirement__audit_id=audit.id,
            requirement__tests__result='not_tested',
            requirement__exclude_in_report=False,
        )
        not_tested_criteria_ids = not_tested_criteria_requirements.values_list(
            'criteria_id', flat=True
        ).distinct()
        not_tested_criteria = Criteria.objects.filter(id__in=not_tested_criteria_ids)
        not_tested_controls_ids = not_tested_criteria_requirements.values_list(
            'requirement_id', flat=True
        ).distinct()
        not_tested_controls = Requirement.objects.filter(id__in=not_tested_controls_ids)

        requirement_ids = (
            CriteriaRequirement.objects.filter(
                criteria__audit_id=audit.id,
                requirement__audit_id=audit.id,
                requirement__exclude_in_report=False,
            )
            .values_list('requirement_id', flat=True)
            .distinct()
        )

        exceptions_noted_requirements = get_requirements_by_args(
            {
                'audit_id': audit.id,
            }
        ).filter(id__in=requirement_ids, tests__result='exceptions_noted')

        has_qualified_criteria = (
            get_criteria_by_audit_id(audit.id).filter(is_qualified=True).exists()
        )

        return {
            "client": organization.name,
            "company_legal_name": organization.legal_name,
            "company_logo": organization.logo.url if organization.logo else None,
            "system_name": organization.system_name
            if organization.system_name
            else SYSTEM_NAME,
            "review_period": review_period,
            "TSCs": get_trust_service_categories(
                audit_configuration['trust_services_categories']
            ),
            "has_section_v": audit.report_sections.filter(section=SECTION_5).exists(),
            "not_tested_criteria": not_tested_criteria,
            "not_tested_controls": not_tested_controls,
            'has_exceptions_noted_requirements': len(exceptions_noted_requirements)
            != 0,
            'has_qualified_criteria': has_qualified_criteria,
        }


class SOC2Type2Section2(Section2):
    def _generate_context(self):
        audit = self.audit
        organization = audit.organization
        audit_configuration = audit.audit_configuration

        start_period_unformatted, end_period_unformatted = audit_configuration[
            'as_of_date'
        ].split(',')
        start_period = str_date_to_date_formatted(start_period_unformatted).strftime(
            MMMM_DD_YYYY
        )
        end_period = str_date_to_date_formatted(end_period_unformatted).strftime(
            MMMM_DD_YYYY
        )
        review_period = f'{start_period} to {end_period}'
        not_tested_criteria_requirements = CriteriaRequirement.objects.filter(
            criteria__audit_id=audit.id,
            requirement__audit_id=audit.id,
            requirement__tests__result='not_tested',
            requirement__exclude_in_report=False,
        )
        not_tested_controls_ids = not_tested_criteria_requirements.values_list(
            'requirement_id', flat=True
        ).distinct()
        not_tested_controls = Requirement.objects.filter(id__in=not_tested_controls_ids)
        has_qualified_criteria = (
            get_criteria_by_audit_id(audit.id).filter(is_qualified=True).exists()
        )

        return {
            "client": organization.name,
            "company_legal_name": organization.legal_name,
            "system_name": organization.system_name
            if organization.system_name
            else SYSTEM_NAME,
            "review_period": review_period,
            "TSCs": get_trust_service_categories(
                audit_configuration['trust_services_categories']
            ),
            "not_tested_controls": not_tested_controls,
            'has_qualified_criteria': has_qualified_criteria,
        }


class SOC2Type2Section3(Section3):
    # This logic will be probably used when the new flow for handling section 3
    # from type 1 into type 2 is defined
    """
    def create_section_file(self):
        past_audit = self.audit.organization.audits.filter(
            audit_framework_type__audit_type="SOC_2_TYPE_1",
            status__requested=True,
            status__initiated=True,
            status__fieldwork=True,
            status__in_draft_report=True,
            status__completed=True,
        ).exclude(
            Q(status__draft_report_file_generated__isnull=True)
            | Q(status__draft_report_file_generated__exact='')
        )
        if past_audit.exists():
            file = str(
                past_audit[:1][0]
                .status.first()
                .draft_report_file_generated.read()
                .decode('utf-8')
            )
            start = file.find('<h1 id="mcetoc_1fiubplrmme" class="pb_before">')
            end = file.find('<div id="section-IV-delimitator"></div>')

            context = self._generate_context()
            section_name = (
                f"Section III: {context.get('client')}’s Description of its"
                f" {context.get('system_name')} for the period"
                f" {context.get('review_period')}"
            )

            file_content = '\n'.join([HTML_INIT_CODE, file[start:end], HTML_END_CODE])

            old_section_3 = File(
                name=f'{self.section}.html', file=io.BytesIO(file_content.encode())
            )
            return {
                'file': old_section_3,
                'section': self.section,
                'name': section_name,
            }
        return super().create_section_file()
    """

    def _generate_context(self):
        audit = self.audit
        organization = audit.organization
        audit_configuration = audit.audit_configuration

        start_period_unformatted, end_period_unformatted = audit_configuration[
            'as_of_date'
        ].split(',')
        start_period = str_date_to_date_formatted(start_period_unformatted).strftime(
            MMMM_DD_YYYY
        )
        end_period = str_date_to_date_formatted(end_period_unformatted).strftime(
            MMMM_DD_YYYY
        )
        review_period = f'{start_period} to {end_period}'
        return {
            "client": organization.name,
            "company_legal_name": organization.legal_name,
            "system_name": organization.system_name
            if organization.system_name
            else SYSTEM_NAME,
            "review_period": review_period,
            "TSCs": get_trust_service_categories(
                audit_configuration['trust_services_categories']
            ),
            'TSC_list': audit_configuration['trust_services_categories'],
            'sso_cloud_provider': get_sso_cloud_provider(organization),
            'sso_cloud_providers_quantity': get_sso_cloud_providers_quantity(
                organization
            ),
            'LCL_4': get_requirement_description_for_report('LCL-4', audit.id),
            'LCL_5': get_requirement_description_for_report('LCL-5', audit.id),
            'LCL_13': get_requirement_description_for_report('LCL-13', audit.id),
            'LCL_20': get_requirement_description_for_report('LCL-20', audit.id),
            'LCL_45': get_requirement_description_for_report('LCL-45', audit.id),
            'LCL_46': get_requirement_description_for_report('LCL-46', audit.id),
            'category': 'categories'
            if len(audit_configuration['trust_services_categories']) > 1
            else 'category',
        }


class SOC2Type2Section4(Section4):
    def _generate_context(self):
        audit = self.audit
        organization = audit.organization
        audit_configuration = audit.audit_configuration
        start_period_unformatted, end_period_unformatted = audit_configuration[
            'as_of_date'
        ].split(',')
        start_period = str_date_to_date_formatted(start_period_unformatted).strftime(
            MMMM_DD_YYYY
        )
        end_period = str_date_to_date_formatted(end_period_unformatted).strftime(
            MMMM_DD_YYYY
        )
        review_period = f'{start_period} to {end_period}'
        requirements = get_requirements(audit)

        return {
            "client": organization.name,
            "review_period": review_period,
            "TSCs": get_trust_service_categories(
                audit_configuration['trust_services_categories']
            ),
            'requirements': requirements,
            'LCL_0': get_requirement_description_for_report('LCL-0', audit.id),
            **build_criteria_table(audit.id),
        }


class SOC2Type2Section5(Section5):
    def _generate_context(self):
        audit = self.audit
        organization = audit.organization
        requirement_ids = (
            CriteriaRequirement.objects.filter(
                criteria__audit_id=audit.id,
                requirement__audit_id=audit.id,
                requirement__exclude_in_report=False,
            )
            .values_list('requirement_id', flat=True)
            .distinct()
        )

        requirements = get_requirements_by_args(
            {
                'audit_id': audit.id,
            }
        ).filter(id__in=requirement_ids, tests__result='exceptions_noted')

        formatted_requirements = [
            {
                'display_id': requirement.display_id,
                'description': requirement.description,
                'tests': get_requirement_tests(requirement).filter(
                    result='exceptions_noted'
                ),
            }
            for requirement in requirements
        ]

        return {"client": organization.name, "requirements": formatted_requirements}


class SOC2Type2SectionsFactory(SectionsFactory):
    def create_section_1(self) -> Union[dict, None]:
        return SOC2Type2Section1(self.audit).create_section_file()

    def create_section_2(self) -> Union[dict, None]:
        return SOC2Type2Section2(self.audit).create_section_file()

    def create_section_3(self) -> Union[dict, None]:
        return SOC2Type2Section3(self.audit).create_section_file()

    def create_section_4(self) -> Union[dict, None]:
        return SOC2Type2Section4(self.audit).create_section_file()

    def create_section_5(self) -> Union[dict, None]:
        return SOC2Type2Section5(self.audit).create_section_file()

from django.core.files import File

from audit.constants import (
    AUDIT_FRAMEWORK_TYPES_DICT,
    SECTION_1,
    SECTION_2,
    SECTION_3,
    SECTION_4,
    SECTION_5,
    SOC_2_TYPE_1,
    SOC_2_TYPE_2,
)
from audit.models import Audit
from audit.sections_factory.SOC2_Type1_sections_factory import SOC2Type1SectionsFactory
from audit.sections_factory.SOC2_Type2_sections_factory import SOC2Type2SectionsFactory


class SectionFactoryClient:
    def __init__(self, audit: Audit):
        self.audit = audit
        self._configure_client()

    def _configure_client(self):
        if (
            self.audit.audit_framework_type.audit_type
            == AUDIT_FRAMEWORK_TYPES_DICT[SOC_2_TYPE_2]
        ):
            self.factory = SOC2Type2SectionsFactory(self.audit)

        if (
            self.audit.audit_framework_type.audit_type
            == AUDIT_FRAMEWORK_TYPES_DICT[SOC_2_TYPE_1]
        ):
            self.factory = SOC2Type1SectionsFactory(self.audit)

    def generate_all_sections(self) -> list[File]:
        factory = getattr(self, 'factory', None)
        if factory is None:
            return []

        section_files = [
            factory.create_section_1(),
            factory.create_section_2(),
            factory.create_section_3(),
            factory.create_section_4(),
            factory.create_section_5(),
        ]
        return [file for file in section_files if file is not None]

    def generate_section(self, section: str):
        if section == SECTION_1:
            return self.factory.create_section_1()
        if section == SECTION_2:
            return self.factory.create_section_2()
        if section == SECTION_3:
            return self.factory.create_section_3()
        if section == SECTION_4:
            return self.factory.create_section_4()
        if section == SECTION_5:
            return self.factory.create_section_5()

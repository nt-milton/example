from audit.constants import SECTION_1, SECTION_2, SECTION_3, SECTION_4, SECTION_5
from audit.models import Audit
from auditor.report.report_generator.report_builder import ReportBuilder
from fieldwork.models import Requirement

LANDSCAPE_ORIENTATION = 'Landscape'


class ReportDirector:
    def __init__(self, audit: Audit):
        self._builder = ReportBuilder(audit=audit)
        self._audit = audit

    def create_soc_2_draft_report_pdf(self):
        self._builder.add_section_1()
        self._builder.add_section(section=SECTION_2)
        self._builder.add_section(section=SECTION_3)
        self._builder.add_section(section=SECTION_4, orientation=LANDSCAPE_ORIENTATION)
        if self._should_include_section_5():
            self._builder.add_section(
                section=SECTION_5, orientation=LANDSCAPE_ORIENTATION
            )
        self._builder.add_draft_watermark()
        return self._builder.get_pdf()

    def create_soc_2_final_report_pdf(self, report_publish_date=None):
        self._builder.add_section_1(
            is_final_report=True, report_publish_date=report_publish_date
        )
        self._builder.add_section(section=SECTION_2)
        self._builder.add_section(section=SECTION_3)
        self._builder.add_section(section=SECTION_4, orientation=LANDSCAPE_ORIENTATION)
        if self._should_include_section_5():
            self._builder.add_section(
                section=SECTION_5, orientation=LANDSCAPE_ORIENTATION
            )
        return self._builder.get_pdf()

    def create_section_pdf(self, section: str):
        if section == SECTION_1:
            self._builder.add_section_1()
        elif section in [SECTION_2, SECTION_3]:
            self._builder.add_section(section=section)
        elif section in [SECTION_4, SECTION_5]:
            self._builder.add_section(
                section=section, orientation=LANDSCAPE_ORIENTATION
            )
        self._builder.add_draft_watermark()
        return self._builder.get_pdf()

    def _should_include_section_5(self):
        return Requirement.objects.filter(
            tests__result='exceptions_noted', audit_id=self._audit.id
        ).exists()

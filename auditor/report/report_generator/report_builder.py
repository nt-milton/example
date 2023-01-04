import datetime
import os
import tempfile
import typing as t

import pdfkit
import pypdftk
from django.template.loader import render_to_string

from audit.constants import HTML_END_CODE, HTML_INIT_CODE, SECTION_1
from audit.models import AuditReportSection
from laika.utils.dates import MMMM_DD_YYYY, str_date_to_date_formatted

DRAFT_VERSION = 'draft'
FINAL_VERSION = 'final'
PDF_MARGIN = '0.8in'

HTML_SUFFIX = '.html'
PDF_SUFFIX = '.pdf'

SIGNATURE_PLACEHOLDER = '[Signature]'
SIGNATURE_ID = 'id="signature-placeholder"'

REPORT_DATE_PLACEHOLDER = '[Date final audit report is issued]'
REPORT_DATE_ID = 'report-publish-date'

PORTRAIT_ORIENTATION = 'Portrait'

BASE_PDF_OPTIONS = {
    'margin-top': PDF_MARGIN,
    'margin-right': PDF_MARGIN,
    'margin-bottom': PDF_MARGIN,
    'margin-left': PDF_MARGIN,
    'load-error-handling': 'skip',
    'orientation': PORTRAIT_ORIENTATION,
}


class ReportBuilder:
    def __init__(self, audit):
        self.report = None
        self.audit = audit
        self.files_to_remove = []
        self.header_file = None
        self.footer_file = None
        self.header_and_footer_current_orientation = ''

    def __del__(self):
        self.reset()

    def reset(self):
        for file_path in self.files_to_remove:
            if os.path.exists(file_path):
                os.remove(file_path)
        self.report = None
        self.header_file = None
        self.footer_file = None
        self.files_to_remove = []
        self.header_and_footer_current_orientation = ''

    def add_section_1(
        self, is_final_report: bool = False, report_publish_date: str = None
    ):
        report_section = self._get_report_section(SECTION_1)
        if report_section is not None:
            report_section_html = self._get_section_html(report_section)
            report_cover_html, section_1_html = self._separate_section_1(
                report_section_html
            )
            if is_final_report:
                section_1_html = section_1_html.replace(
                    SIGNATURE_PLACEHOLDER, self._get_signature_html()
                ).replace(SIGNATURE_ID, '')
                section_1_html = self._add_publish_date(
                    section_1_html, report_publish_date
                )

            cover_file = self._create_temporary_file(
                report_cover_html.encode('utf-8'), suffix=HTML_SUFFIX
            )
            self._create_header_and_footer_files(SECTION_1)
            section_1_options = {**BASE_PDF_OPTIONS}
            section_1_options['header-html'] = self.header_file.name
            section_1_options['footer-html'] = self.footer_file.name

            section_1_pdf_bytes = pdfkit.from_string(
                section_1_html,
                False,
                section_1_options,
                cover=cover_file.name,
            )
            section_1_pdf = self._create_temporary_file(section_1_pdf_bytes, PDF_SUFFIX)
            self._merge_new_content_to_report(section_1_pdf)

    def add_section(self, section: str, orientation=PORTRAIT_ORIENTATION):
        report_section = self._get_report_section(section)
        if report_section is not None:
            section_html = self._get_section_html(report_section)

            self._create_header_and_footer_files(section)
            section_options = {**BASE_PDF_OPTIONS}
            section_options['header-html'] = self.header_file.name
            section_options['footer-html'] = self.footer_file.name
            section_options['orientation'] = orientation
            if self.report is not None:
                start_page_number = self._get_report_pages_number()
                section_options['page-offset'] = start_page_number

            section_pdf_bytes = pdfkit.from_string(
                section_html,
                False,
                section_options,
            )
            section_pdf = self._create_temporary_file(section_pdf_bytes, PDF_SUFFIX)
            self._merge_new_content_to_report(section_pdf)

    def add_draft_watermark(self):
        watermark_html_file = self._create_temporary_file(
            file_bytes=render_to_string('report-v2-watermark-template.html').encode(
                'utf-8'
            ),
            suffix=HTML_SUFFIX,
        )

        watermark_pdf = pdfkit.from_file(watermark_html_file.name, False)

        watermark_file = self._create_temporary_file(
            file_bytes=watermark_pdf, suffix=PDF_SUFFIX
        )

        self.report = open(
            pypdftk.stamp(
                stamp_pdf_path=watermark_file.name, pdf_path=self.report.name
            ),
            'rb',
        )

    def get_pdf(self):
        report = self.report
        self.reset()
        return report

    def _get_report_pages_number(self):
        return pypdftk.get_num_pages(self.report.name)

    def _get_report_section(self, section: str):
        report_section = list(self.audit.report_sections.filter(section=section))
        return report_section[0] if len(report_section) else None

    def _get_section_html(self, section: AuditReportSection):
        return section.file.read().decode('UTF-8')

    def _separate_section_1(self, report_html: str):
        cover_content, section_1_content = report_html.split(
            '<div id="cover-delimitator"></div>'
        )
        report_cover_html = cover_content + HTML_END_CODE
        section_1_html = HTML_INIT_CODE + section_1_content
        return report_cover_html, section_1_html

    def _create_header_and_footer_files(
        self, section: str, orientation=PORTRAIT_ORIENTATION
    ):
        header_file_path = (
            'report-v2-header-template.html'
            if orientation == PORTRAIT_ORIENTATION
            else 'report-v2-landscape-header-template.html'
        )
        footer_file_path = (
            'report-v2-footer-template.html'
            if orientation == PORTRAIT_ORIENTATION
            else 'report-v2-landscape-footer-template.html'
        )
        header_context = {
            'audit_type': self.audit.audit_type,
            'legal_name': self.audit.organization.legal_name,
            'section': section,
        }

        header_file = self._create_temporary_file(
            file_bytes=render_to_string(header_file_path, header_context).encode(
                'utf-8'
            ),
            suffix=HTML_SUFFIX,
        )

        footer_file = self._create_temporary_file(
            file_bytes=render_to_string(footer_file_path).encode('utf-8'),
            suffix=HTML_SUFFIX,
        )

        self.header_and_footer_current_orientation = orientation
        self.header_file = header_file
        self.footer_file = footer_file

    def _merge_new_content_to_report(self, new_content_file):
        if self.report is None:
            self.report = open(new_content_file.name, 'rb')
        else:
            self.files_to_remove.append(self.report.name)
            self.report = open(
                pypdftk.concat(
                    files=[
                        self.report.name,
                        new_content_file.name,
                    ]
                ),
                'rb',
            )

    def _create_temporary_file(self, file_bytes: bytes, suffix: str) -> t.IO[bytes]:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary_file:
            temporary_file.write(file_bytes)
        self.files_to_remove.append(temporary_file.name)
        return temporary_file

    def _get_signature_html(self) -> str:
        return f'''
            <span style="font-family: 'Vujahday Script', cursive;font-size: 24pt;">
                {self.audit.audit_firm.signature_text}
            </span>
        '''

    def _get_formatted_publish_date(self, report_publish_date: str = None) -> str:
        if not report_publish_date:
            report_updated_at = self.audit.status.first().final_report_updated_at
            formatted_date = (
                report_updated_at if report_updated_at else datetime.datetime.now()
            )
            return formatted_date.strftime(MMMM_DD_YYYY)
        date = str_date_to_date_formatted(report_publish_date)
        return date.strftime(MMMM_DD_YYYY)

    def _add_publish_date(self, html: str, report_publish_date: str = None) -> str:
        formatted_date = self._get_formatted_publish_date(report_publish_date)
        return html.replace(REPORT_DATE_PLACEHOLDER, formatted_date).replace(
            f'id="{REPORT_DATE_ID}"', ''
        )

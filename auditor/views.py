import json
import os
import tempfile
import typing as t

import pdfkit
import pypdftk
from django.http import HttpResponseBadRequest
from django.http.response import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from audit.constants import DRAFT_REPORT_SECTIONS_DICT, HTML_INIT_CODE
from audit.models import Audit
from auditor.report.report_generator.report_builder import DRAFT_VERSION, FINAL_VERSION
from auditor.report.report_generator.report_director import ReportDirector
from laika.constants import OCTET_STREAM_CONTENT_TYPE
from laika.decorators import audit_service
from laika.utils.files import get_file_extension

from .utils import validate_auditor_get_draft_report_file

PDF_MARGIN = '0.8in'

HTML_SUFFIX = '.html'
PDF_SUFFIX = '.pdf'

pdf_options = {
    'margin-top': PDF_MARGIN,
    'margin-right': PDF_MARGIN,
    'margin-bottom': PDF_MARGIN,
    'margin-left': PDF_MARGIN,
    'load-error-handling': 'skip',
    'orientation': 'Portrait',
}


# Type ignored because _TemporaryFileWrapper is "module-private".
def create_temporary_file(file_bytes: bytes, suffix: str) -> t.IO[bytes]:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary_file:
        temporary_file.write(file_bytes)
    return temporary_file


def template_files(
    header_context: dict[str, str], cover_html: str, header_path: str, footer_path: str
):
    header_file = create_temporary_file(
        file_bytes=render_to_string(header_path, header_context).encode('utf-8'),
        suffix=HTML_SUFFIX,
    )

    footer_file = create_temporary_file(
        file_bytes=render_to_string(footer_path).encode('utf-8'), suffix=HTML_SUFFIX
    )

    cover_file = create_temporary_file(cover_html.encode('utf-8'), suffix=HTML_SUFFIX)

    return header_file, footer_file, cover_file


def create_watermark_file():
    try:
        watermark_html_file = create_temporary_file(
            file_bytes=render_to_string('report-watermark-template.html').encode(
                'utf-8'
            ),
            suffix=HTML_SUFFIX,
        )

        watermark_pdf = pdfkit.from_file(watermark_html_file.name, False)

        return create_temporary_file(file_bytes=watermark_pdf, suffix=PDF_SUFFIX)
    finally:
        os.remove(watermark_html_file.name)


def separate_draft_report_html(draft_report_html: str) -> t.Tuple[str, str, str]:
    draft_report_html_chunks = draft_report_html.split(
        '<div id="cover-delimitator"></div>'
    )
    cover_html = draft_report_html_chunks[0]

    draft_report_html = (
        HTML_INIT_CODE + draft_report_html_chunks[1]
        if len(draft_report_html_chunks) > 1
        else ''
    )

    draft_report_html_chunks = draft_report_html.split(
        '<div id="section-IV-delimitator"></div>'
    )
    portrait_draft_report_html = (
        draft_report_html_chunks[0] if draft_report_html_chunks[0] else ''
    )
    landscape_draft_report = (
        draft_report_html_chunks[1] if len(draft_report_html_chunks) > 1 else ''
    )

    return cover_html, portrait_draft_report_html, landscape_draft_report


def get_pdf_from_draft_report_html(audit: Audit, draft_report_html: str) -> t.BinaryIO:
    merged_landscape_portrait = None
    draft_report_file: t.IO[bytes]

    (
        cover_html,
        portrait_draft_report_html,
        landscape_draft_report,
    ) = separate_draft_report_html(draft_report_html)

    header_context = {'audit_type': audit.audit_type, 'client': audit.organization.name}

    draft_report_pdf_options = {**pdf_options}

    try:
        header_file, footer_file, cover_file = template_files(
            header_context,
            cover_html,
            'report-header-template.html',
            'report-footer-template.html',
        )

        draft_report_pdf_options['header-html'] = header_file.name
        draft_report_pdf_options['footer-html'] = footer_file.name

        portrait_draft_report_pdf = pdfkit.from_string(
            portrait_draft_report_html,
            False,
            draft_report_pdf_options,
            cover=cover_file.name,
        )

        if landscape_draft_report:
            extra_files = template_files(
                header_context,
                cover_html,
                'report-landscape-header-template.html',
                'report-landscape-footer-template.html',
            )
            portrait_draft_report_file = create_temporary_file(
                file_bytes=portrait_draft_report_pdf, suffix=PDF_SUFFIX
            )
            draft_report_pdf_options['orientation'] = 'Landscape'
            draft_report_pdf_options['page-offset'] = pypdftk.get_num_pages(
                pdf_path=portrait_draft_report_file.name
            )
            draft_report_pdf_options['header-html'] = extra_files[0].name
            draft_report_pdf_options['footer-html'] = extra_files[1].name
            landscape_draft_report_pdf = pdfkit.from_string(
                input=HTML_INIT_CODE + landscape_draft_report,
                output_path=False,
                options=draft_report_pdf_options,
            )
            landscape_draft_report_file = create_temporary_file(
                file_bytes=landscape_draft_report_pdf, suffix=PDF_SUFFIX
            )

            merged_landscape_portrait = pypdftk.concat(
                files=[
                    portrait_draft_report_file.name,
                    landscape_draft_report_file.name,
                ]
            )

        if merged_landscape_portrait:
            draft_report_file = open(merged_landscape_portrait, 'rb')
        else:
            draft_report_file = create_temporary_file(
                file_bytes=portrait_draft_report_pdf, suffix=PDF_SUFFIX
            )

        watermark_file = create_watermark_file()

        draft_report_pdf_with_watermark_file = pypdftk.stamp(
            stamp_pdf_path=watermark_file.name, pdf_path=draft_report_file.name
        )

        draft_report_with_watermark_pdf = open(
            draft_report_pdf_with_watermark_file, 'rb'
        )
    finally:
        os.remove(header_file.name)
        os.remove(footer_file.name)
        os.remove(cover_file.name)

        if landscape_draft_report:
            os.remove(extra_files[0].name)
            os.remove(extra_files[1].name)
            os.remove(landscape_draft_report_file.name)
            os.remove(portrait_draft_report_file.name)

        os.remove(watermark_file.name)
        os.remove(draft_report_file.name)
        os.remove(draft_report_pdf_with_watermark_file)

    return draft_report_with_watermark_pdf


@csrf_exempt
@require_POST
@audit_service(
    atomic=False,
    permission='audit.view_audit',
    exception_msg='Failed to get audit draft report PDF.',
    revision_name='Get audit draft report PDF',
)
def get_draft_report_pdf(request):
    body_obj = json.loads(request.body.decode('utf-8'))
    audit_id = body_obj.get('auditId')

    audit = Audit.objects.get(id=audit_id)

    validate_auditor_get_draft_report_file(audit)

    audit_status = audit.status.first()
    draft_report_file = audit_status.draft_report_file_generated

    draft_report_html = draft_report_file.file.read().decode('UTF-8')

    draft_report_pdf = get_pdf_from_draft_report_html(audit, draft_report_html)

    response = HttpResponse(draft_report_pdf, content_type='application/pdf')
    response[
        'Content-Disposition'
    ] = f'draftreport;filename="draft-report-audit-{audit_id}.pdf"'

    return response


@csrf_exempt
@require_POST
@audit_service(
    atomic=False,
    permission='audit.view_audit',
    exception_msg='Failed to get audit uploaded draft report PDF.',
    revision_name='Get audit uploaded draft report PDF',
)
def get_uploaded_draft_report(request):
    body_obj = json.loads(request.body.decode('utf-8'))
    audit_id = body_obj.get('auditId')

    audit = Audit.objects.get(id=audit_id)

    audit_status = audit.status.first()
    draft_report = audit_status.draft_report

    file_extension = get_file_extension(str(draft_report.file))

    response = HttpResponse(draft_report, content_type=OCTET_STREAM_CONTENT_TYPE)
    file_name = f'{audit.name}{file_extension}'
    response['Content-Disposition'] = f'attachment;filename="{file_name}"'

    return response


@csrf_exempt
@require_POST
@audit_service(
    atomic=False,
    permission='audit.view_audit',
    exception_msg='Failed to generate draft report section PDF.',
    revision_name='Generate draft report section PDF',
)
def generate_draft_report_section_pdf(request):
    body_obj = json.loads(request.body.decode('utf-8'))
    audit_id = body_obj.get('auditId')
    section = body_obj.get('section')

    if (
        not audit_id
        or not section
        or section not in DRAFT_REPORT_SECTIONS_DICT.values()
    ):
        return HttpResponseBadRequest()

    audit = Audit.objects.get(id=audit_id)

    report_section = audit.report_sections.get(section=section)
    report_director = ReportDirector(audit)
    pdf_section = report_director.create_section_pdf(section)

    response = HttpResponse(pdf_section, content_type=OCTET_STREAM_CONTENT_TYPE)

    file_name = (
        f'Draft {report_section.name} - {audit.name} - '
        f'{audit.audit_framework_type.certification.name}{PDF_SUFFIX}'
    ).replace(':', '')

    file_name = file_name.encode('ascii', errors='ignore').decode()
    response['Access-Control-Expose-Headers'] = 'Template-Filename'
    response['Content-Disposition'] = f'attachment; filename="{file_name}"'
    response['Template-Filename'] = file_name

    return response


@csrf_exempt
@require_POST
@audit_service(
    atomic=False,
    permission='audit.view_audit',
    exception_msg='Failed to generate draft report PDF.',
    revision_name='Generate draft report PDF',
)
def generate_report_pdf(request):
    body_obj = json.loads(request.body.decode('utf-8'))
    audit_id = body_obj.get('auditId')
    version = body_obj.get('version')
    report_publish_date = body_obj.get('reportPublishDate')

    if not audit_id or version not in [FINAL_VERSION, DRAFT_VERSION]:
        return HttpResponseBadRequest()

    audit = Audit.objects.get(id=audit_id)

    report_director = ReportDirector(audit)
    if version == FINAL_VERSION:
        report = report_director.create_soc_2_final_report_pdf(report_publish_date)
    else:
        report = report_director.create_soc_2_draft_report_pdf()

    file_name = (
        f'{version.capitalize()} - {audit.organization.name} -'
        f' {audit.audit_framework_type.certification.name}{PDF_SUFFIX}'.replace(':', '')
    )

    response = HttpResponse(report, content_type=OCTET_STREAM_CONTENT_TYPE)

    file_name = file_name.encode('ascii', errors='ignore').decode()
    response['Access-Control-Expose-Headers'] = 'Template-Filename'
    response['Content-Disposition'] = f'attachment; filename="{file_name}"'
    response['Template-Filename'] = file_name

    return response

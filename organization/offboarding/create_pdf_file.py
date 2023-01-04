import pdfkit
from django.core.files import File
from django.template import loader

from laika.utils import pdf


def create_pdf_file(checklist):
    document_template = loader.render_to_string(
        'offboarding/employee_run.html', checklist
    )

    options = {
        'page-size': 'Letter',
        'header-spacing': 10,
        'footer-spacing': 18,
        'dpi': 72,
        # This flag tells wkhtmltopdf to use the @media print css rules.
        'print-media-type': '',
    }

    template_pdf = pdfkit.from_string(document_template, False, options=options)
    report_pdf = pdf.merge(template_pdf)
    return File(name='offboarding.pdf', file=report_pdf)

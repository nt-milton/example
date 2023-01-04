import io
from typing import Union

import pdfkit
from PyPDF2 import PdfMerger

from laika.aws import dynamo
from laika.utils.templates import render_template


def render_template_to_pdf(template, context, time_zone=None, orientation='Portrait'):
    html = render_template(template, context, time_zone)

    options = {
        'page-size': 'Letter',
        'encoding': "UTF-8",
        'enable-local-file-access': None,
        'orientation': orientation,
    }

    return pdfkit.from_string(html, False, options)


def convert_html_text_to_pdf(html_text) -> bytes:
    return pdfkit.from_string(html_text, False)


def merge(*pdfs: Union[str, bytes, io.BytesIO]) -> io.BytesIO:
    """
    Merges multiple PDFs into a single PDF.

    @param: pdfs Input files, can be a str with file's path or stream of bytes.
    """
    merger = PdfMerger()
    for pdf in pdfs:
        if isinstance(pdf, bytes):
            pdf = io.BytesIO(pdf)
        merger.append(fileobj=pdf)

    pdf_bytes = io.BytesIO()
    merger.write(pdf_bytes)
    pdf_bytes.seek(0)
    return pdf_bytes


def get_document_pdf(organization, document_id):
    html_text = dynamo.get_document(organization.id, f'd-{document_id}')
    return convert_html_text_to_pdf(html_text)


def convert_file_to_pdf(file):
    return merge(convert_html_text_to_pdf(file.read().decode('utf-8')))

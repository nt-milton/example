import os

from django.core.files import File

import evidence.constants as constants
from laika.utils.pdf import convert_html_text_to_pdf

DOWNLOAD_PAPER_EXT = '.pdf'


def add_file_to_zip(evidence_name, evidence_file, zip_folder):
    file_bytes = evidence_file.read()
    zip_folder.writestr(evidence_name, file_bytes)


def _get_file_name_without_ext(evidence):
    if evidence.type == constants.LAIKA_PAPER:
        evidence_name = os.path.basename(os.path.splitext(evidence.name)[0])
        return f'{evidence_name}{DOWNLOAD_PAPER_EXT}'

    return evidence.name


def zip_file(evidence, zip_folder):
    if evidence.type in (constants.FILE, constants.OFFICER, constants.TEAM):
        add_file_to_zip(
            evidence.name,
            File(name=_get_file_name_without_ext(evidence), file=evidence.file),
            zip_folder,
        )


def zip_paper(evidence, zip_folder):
    if evidence.type == constants.LAIKA_PAPER:
        zip_folder.writestr(
            _get_file_name_without_ext(evidence),
            convert_html_text_to_pdf(evidence.file.read().decode('utf-8')),
        )

import io
import logging
import os
from zipfile import BadZipFile

from defusedxml.lxml import XML
from django.core.files import File
from docxtpl import DocxTemplate

from laika.utils.exceptions import ServiceException
from laika.utils.office import export_document_bytes
from policy.constants import (
    BAD_FORMATTED_DOCX_DRAFT_FILE_EXCEPTION_MSG,
    INCOMPATIBLE_DRAFT_FILE_FORMAT_EXCEPTION_MSG,
)

logger = logging.getLogger(__name__)

WORD_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
TABLE_TAG = WORD_NAMESPACE + "tbl"
DELETION_TAG = WORD_NAMESPACE + "del"
XML_WORD_NAMESPACE = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
}
EMPTY_PARAGRAPH_AND_PROPERTIES_TAG = '<w:p><w:pPr><w:rPr/></w:pPr><w:r/></w:p>'
EMPTY_TRACKED_PARAGRAPH_TAG = '<w:p><w:r/></w:p>'


def get_validated_docx_file(policy):
    try:
        # Validate if the instance creation is sucessful
        # meaning that the docx file has not missing metadata
        DocxTemplate(policy.draft)
        return policy.draft
    except KeyError:
        # Use document server conversion service
        # to fix missing metadata for docx file.
        converted_docx_bytes = export_document_bytes(
            policy.draft_key, policy.name, policy.draft.url, output_format='docx'
        )
        return File(name=os.path.basename(policy.draft.name), file=converted_docx_bytes)
    except (ValueError, BadZipFile):
        # The draft file is a pdf or doc,
        # formats not supported by DocxTemplate.
        logger.error(f'Draft policy {policy.id} must be a docx file')
        raise ServiceException(INCOMPATIBLE_DRAFT_FILE_FORMAT_EXCEPTION_MSG)


def remove_proposed_changes(draft, policy_id):
    try:
        doc = DocxTemplate(draft)
    except KeyError:
        logger.error(f'Draft policy {policy_id} has missing XML metadata')
        raise ServiceException(BAD_FORMATTED_DOCX_DRAFT_FILE_EXCEPTION_MSG)
    doc.map_tree(remove_changes(XML(doc.get_xml())))
    doc.map_tree(remove_tracked_empty_paragraphs(doc))

    file_stream = io.BytesIO()
    doc.save(file_stream)
    return file_stream


def remove_tracked_empty_paragraphs(doc):
    doc_xml = (
        doc.get_xml()
        .replace(EMPTY_PARAGRAPH_AND_PROPERTIES_TAG, '')
        .replace(EMPTY_TRACKED_PARAGRAPH_TAG, '')
    )
    return XML(doc_xml)


def remove_changes_in_table(body):
    table_rows = body.findall('w:tr', XML_WORD_NAMESPACE)
    for row_index, row in enumerate(table_rows, start=0):
        if len(row.findall('w:trPr/w:ins', XML_WORD_NAMESPACE)) > 0:
            body.remove(row)
    return body


def remove_changes(body):
    if body.tag == TABLE_TAG:
        body = remove_changes_in_table(body)
    for element_index, element in enumerate(body, start=0):
        remove_additions(element)
        remove_deletions(element)
        body[element_index] = remove_changes(element)
    return body


def remove_additions(element):
    for addition in element.findall('w:ins', XML_WORD_NAMESPACE):
        element.remove(addition)


def remove_deletions(element):
    for child_index, child in enumerate(element, start=0):
        if child.tag == DELETION_TAG:
            if len(child) > 0:
                child = child[0]
                element[child_index] = child
            else:
                element.remove(child)

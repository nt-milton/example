import logging
import os

import docx
from bs4 import BeautifulSoup

logger = logging.getLogger('files')


def get_docx_file_content(file, entity_id):
    full_text = ''
    try:
        doc = docx.Document(file)
        full_text = '\n'.join([p.text for p in doc.paragraphs])
    except IOError:
        logger.exception(f'There was an error opening the docx file for: {entity_id}')
    return full_text


def get_html_file_content(html, entity_id):
    full_text = ''

    try:
        soup = BeautifulSoup(html, features='html.parser')

        # Remove all script, style and image elements
        for element in soup(['script', 'style', 'img']):
            element.extract()
        full_text = soup.get_text()
    except IOError:
        logger.exception(f'There was an error opening the html file for: {entity_id}')
    return full_text


def get_file_extension(name):
    _, extension = os.path.splitext(name)
    return extension


def filename_has_extension(name, extension='.docx'):
    file_extension = get_file_extension(name)
    return file_extension == extension

import io
from json import JSONDecodeError

import requests

from laika import settings
from laika.utils.exceptions import ServiceException


def get_document_url(key, title, url, output_format):
    response = requests.post(
        f'{settings.DOCUMENT_SERVER_URL}/ConvertService.ashx',
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
        json={
            'async': False,
            'filetype': 'docx',
            'key': key,
            'outputtype': output_format,
            'title': title,
            'url': url,
        },
    )
    try:
        return response.json()['fileUrl']
    except (JSONDecodeError, KeyError):
        message = (
            'Document service parse error(code: '
            f'{response.status_code} content: {response.text})'
        )
        raise ServiceException(message)


def export_document_bytes(key, title, url, output_format='pdf'):
    file_url = get_document_url(key, title, url, output_format)
    document_response = requests.get(file_url, stream=True)
    document_response.raise_for_status()

    return io.BytesIO(document_response.raw.read())


def export_document_url(key, title, url, output_format='pdf'):
    file_url = get_document_url(key, title, url, output_format)
    file_url = (
        file_url.replace('document-server', 'localhost')
        if 'document-server' in file_url
        else file_url
    )
    file_url = (
        file_url.replace('attachment', 'inline')
        if 'attachment' in file_url
        else file_url
    )
    return (
        file_url
        + '#scrollbar=0&toolbar=0&statusbar=0&messages=0&navpanes=0&page=pagenum'
    )

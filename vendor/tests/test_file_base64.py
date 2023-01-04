from unittest.mock import MagicMock

from botocore.exceptions import ClientError
from django.core.files.uploadedfile import SimpleUploadedFile

from vendor.views import file_to_base64


def test_returns_empty_string_when_passing_none():
    data = file_to_base64(None)
    assert data == ''


def test_file_to_base64():
    fake_file = SimpleUploadedFile('image.png', b'Hello World')
    data = file_to_base64(fake_file)
    assert data == 'SGVsbG8gV29ybGQ='


def test_exception_log(caplog):
    file = MagicMock()
    file.read = MagicMock()
    file.read.side_effect = Exception('oops')
    data = file_to_base64(file)
    assert data == ''
    assert 'ERROR' in caplog.text
    assert 'oops' in caplog.text


def test_os_error_log(caplog):
    message = 'File does not exist: media/test.png'
    file = MagicMock()
    file.read = MagicMock()
    file.read.side_effect = OSError(message)
    data = file_to_base64(file)
    assert data == ''
    assert 'WARNING' in caplog.text
    assert message in caplog.text


def test_client_error_log(caplog):
    message = 'An error occurred'
    file = MagicMock()
    file.read = MagicMock()
    file.read.side_effect = ClientError({}, 'read')
    data = file_to_base64(file)
    assert data == ''
    assert 'WARNING' in caplog.text
    assert message in caplog.text

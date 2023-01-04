import pytest

from laika.tests import mock_responses
from laika.utils.exceptions import ServiceException
from laika.utils.office import get_document_url


@pytest.fixture
def empty_response():
    with mock_responses(['{}']):
        yield


def test_document_server_empty(empty_response):
    with pytest.raises(ServiceException, match='Document service parse error'):
        get_document_url('key', 'title', 'url', 'json')


@pytest.fixture
def invalid_response():
    with mock_responses(['<html>Internal error</html>']):
        yield


def test_document_server_invalid(invalid_response):
    with pytest.raises(ServiceException, match='Document service parse error'):
        get_document_url('key', 'title', 'url', 'json')


@pytest.fixture
def valid_response():
    with mock_responses(['{"fileUrl":"path"}']):
        yield


def test_document_server_read_url(valid_response):
    url = get_document_url('key', 'title', 'url', 'json')
    assert url == 'path'

from unittest.mock import patch

import pytest
from docusign_esign.client.api_exception import ApiException

from audit.docusign_connection.docusign_connection import DocuSignConnection
from laika.utils.dictionaries import DictToClass

URL = 'https://test.com/test?PowerFormId=thisisMyPowerFormId&env=na4&acct=1234&v=2'


ENVELOPES = DictToClass(
    envelopes=[
        DictToClass(
            envelope_id='1',
            recipients=[DictToClass(email='tanjiro@heylaika.com')],
        )
    ]
)


@pytest.fixture
@patch('audit.docusign_connection.docusign_connection.ApiClient.set_default_header')
@patch('audit.docusign_connection.docusign_connection.ApiClient.request_jwt_user_token')
def docusign_connection(request_jwt_user_token_mock, set_default_header_mock):
    request_jwt_user_token_mock.return_value = DictToClass(access_token='1234')
    set_default_header_mock.return_value = None
    return DocuSignConnection()


@pytest.mark.functional()
@patch('audit.docusign_connection.docusign_connection.EnvelopesApi.get_envelope')
@patch(
    'audit.docusign_connection.docusign_connection.PowerFormsApi.get_power_form_data'
)
def test_get_envelope_status_with_existing_envelope(
    get_power_form_data_mock, get_envelope_mock, docusign_connection: DocuSignConnection
):
    get_envelope_mock.return_value = DictToClass(status='completed')
    get_power_form_data_mock.return_value = ENVELOPES

    assert docusign_connection.get_envelope_status(URL, '@heylaika.com') == 'completed'


@pytest.mark.functional()
@patch('audit.docusign_connection.docusign_connection.EnvelopesApi.get_envelope')
@patch(
    'audit.docusign_connection.docusign_connection.PowerFormsApi.get_power_form_data'
)
def test_get_envelope_status_with_unexisting_envelope(
    get_power_form_data_mock, get_envelope_mock, docusign_connection: DocuSignConnection
):
    get_power_form_data_mock.return_value = ENVELOPES

    assert docusign_connection.get_envelope_status(URL, '@unexisting.com') == 'sent'


@pytest.mark.functional()
@patch('audit.docusign_connection.docusign_connection.EnvelopesApi.get_envelope')
@patch(
    'audit.docusign_connection.docusign_connection.PowerFormsApi.get_power_form_data'
)
def test_get_envelope_status_with_empty_power_form(
    get_power_form_data_mock, get_envelope_mock, docusign_connection: DocuSignConnection
):
    get_power_form_data_mock.side_effect = ApiException()

    assert docusign_connection.get_envelope_status(URL, '@empty.com') == 'sent'


@pytest.mark.functional()
@patch('audit.docusign_connection.docusign_connection.EnvelopesApi.get_envelope')
@patch(
    'audit.docusign_connection.docusign_connection.PowerFormsApi.get_power_form_data'
)
def test_get_envelope_status_with_empty_url(
    get_power_form_data_mock, get_envelope_mock, docusign_connection: DocuSignConnection
):
    assert docusign_connection.get_envelope_status('', '@empty.com') == 'sent'


@pytest.mark.functional()
def test_get_power_form_id_from_url(docusign_connection: DocuSignConnection):
    assert docusign_connection._get_power_form_id_from_url(URL) == 'thisisMyPowerFormId'


@pytest.mark.functional()
def test_is_envelope_completed(docusign_connection: DocuSignConnection):
    assert docusign_connection.is_envelope_completed('completed') is True

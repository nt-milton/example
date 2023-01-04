import base64
from urllib.parse import parse_qs, urlparse

from docusign_esign import ApiClient, EnvelopesApi, PowerFormsApi
from docusign_esign.client.api_exception import ApiException

from laika.settings import DJANGO_SETTINGS


class DocuSignConnection:
    _scopes = ["signature", "impersonation"]
    _API_CLIENT_HOST = DJANGO_SETTINGS.get('DOCUSIGN_API_CLIENT_HOST')

    _OAUTH_HOST_NAME = DJANGO_SETTINGS.get('DOCUSIGN_OAUTH_HOST_NAME')

    _ACCOUNT_ID = DJANGO_SETTINGS.get('DOCUSIGN_ACCOUNT_ID')

    _CLIENT_ID = DJANGO_SETTINGS.get('DOCUSIGN_CLIENT_ID')

    _USER_ID = DJANGO_SETTINGS.get('DOCUSIGN_USER_ID')

    def __init__(self) -> None:
        self.api_client = ApiClient()
        self.api_client.host = self._API_CLIENT_HOST

    def get_envelope_status(self, url: str, email_domain: str) -> str:
        if not self._does_url_and_email_domain_exists(url, email_domain):
            return 'sent'
        self._get_access_token()
        envelope_id = self._get_envelope_id(url, email_domain)
        if envelope_id is None:
            return 'sent'
        envelope_api = EnvelopesApi(self.api_client)
        return envelope_api.get_envelope(
            account_id=self._ACCOUNT_ID, envelope_id=envelope_id
        ).status

    def is_envelope_completed(self, status: str) -> bool:
        return status == 'completed'

    def _get_access_token(self):
        ds_app = self.api_client.request_jwt_user_token(
            client_id=self._CLIENT_ID,
            user_id=self._USER_ID,
            oauth_host_name=self._OAUTH_HOST_NAME,
            private_key_bytes=self._get_private_key_bytes(),
            expires_in=5000,
            scopes=self._scopes,
        )
        access_token = ds_app.access_token
        self.api_client.set_default_header("Authorization", f"Bearer {access_token}")

    def _get_envelope_id(self, url: str, email_domain: str):
        try:
            power_form_id = self._get_power_form_id_from_url(url)
            power_form_api = PowerFormsApi(self.api_client)
            response = power_form_api.get_power_form_data(
                account_id=self._ACCOUNT_ID, power_form_id=power_form_id
            )
            envelope_id = None
            for envelope in response.envelopes:
                for recipient in envelope.recipients:
                    if email_domain in recipient.email:
                        envelope_id = envelope.envelope_id
            return envelope_id
        except (ApiException, KeyError):
            return None

    def _get_private_key_bytes(self):
        key_base64_string = DJANGO_SETTINGS.get('DOCUSIGN_PRIVATE_KEY', '')
        key_base64_bytes = key_base64_string.encode("ascii")
        key_bytes = base64.b64decode(key_base64_bytes)
        return key_bytes

    def _get_power_form_id_from_url(self, url: str) -> str:
        parsed_url = urlparse(url)
        return parse_qs(parsed_url.query)['PowerFormId'][0]

    def _does_url_and_email_domain_exists(self, url: str, email_domain: str) -> bool:
        return bool(url) and bool(email_domain)

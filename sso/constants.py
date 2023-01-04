from laika.settings import OKTA_API_KEY

OKTA_HEADERS = {
    'Accept': 'application/json',
    'Authorization': f'SSWS {OKTA_API_KEY}',
    'Content-Type': 'application/json',
}

OKTA_INSTANCE_URL = 'https://laika.okta.com'

OKTA_IDPS_API = 'api/v1/idps'
OKTA_KEYS_API = f'{OKTA_IDPS_API}/credentials/keys'
OKTA_RULES_API = 'api/v1/policies/00pnroku52tvQErWp5d6/rules'
OKTA_MAPPINGS_API = '/api/v1/mappings'
OKTA_USERS_API = 'api/v1/users'


def get_okta_properties_url(idp_id):
    return f'/api/v1/meta/schemas/apps/{idp_id}/default'


SAML_INTEGRATIONS = (('AZURE', 'Azure AD'), ('GOOGLE', 'Google'), ('OKTA', 'Okta'))

AZURE = 'Azure AD'
GOOGLE = 'Google'
OKTA = 'Okta'

IDP_ACTIVE = 'ACTIVE'
IDP_INACTIVE = 'INACTIVE'

OKTA_GROUPS = {
    'local': '00g18k8ckb9tRRatc5d7',
    'dev': '00g18k8ckb9tRRatc5d7',
    'staging': '00g18k8q7aa7dQPvi5d7',
    'rc': '00g18k8q7aa7dQPvi5d7',
    'prod': '00g18kaa6aVvWArOC5d7',
}

BASE_CERTIFICATE_ID = 'b19a2554-b48c-4d4c-a5e5-af3bc24f318f'

OKTA_DUMMY_URL = 'https://www.test.com'

EXISTING_KEY_ERROR_CODE = 'E0000096'

PENDING_IDP_DATA = 'PENDING_IDP_DATA'
PENDING_DOMAINS = 'PENDING_DOMAINS'
DONE_ENABLED = 'DONE_ENABLED'
DONE_DISABLED = 'DONE_DISABLED'

OKTA_RESPONSE_PROTOCOL = 'protocol'
OKTA_RESPONSE_CREDENTIALS = 'credentials'

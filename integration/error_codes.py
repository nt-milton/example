# Error codes

NONE = '000'
OTHER = '001'
INSUFFICIENT_PERMISSIONS = '002'
MISSING_GITHUB_ORGANIZATION = '003'
DENIAL_OF_CONSENT = '004'
INSUFFICIENT_CONFIG_DATA = '005'
BAD_CLIENT_CREDENTIALS = '006'
EXPIRED_TOKEN = '007'
BAD_GATEWAY = '008'
SERVICE_UNAVAILABLE = '009'
# Note: next time that we need a new error code use 008 - 009 - 010
PROVIDER_SERVER_ERROR = '011'
RESOURCE_NOT_FOUND = '012'
API_LIMIT = '013'
MISSING_GITHUB_APP_INSTALLATION = '014'
PROVIDER_GRAPHQL_ERROR = '015'
CONNECTION_TIMEOUT = '016'
DEFAULT_GRAPHQL_ERROR = '017'
ACCESS_REVOKED = '018'
USER_INPUT_ERROR = '019'
GATEWAY_TIMEOUT = '020'
BAD_REQUEST = '021'

ERROR_CODES = [
    (NONE, 'None'),
    (OTHER, 'Other'),
    (INSUFFICIENT_PERMISSIONS, 'Insufficient Permissions'),
    (MISSING_GITHUB_ORGANIZATION, 'Missing Github Organization'),
    (DENIAL_OF_CONSENT, 'Denial Of Consent'),
    (INSUFFICIENT_CONFIG_DATA, 'Insufficient Config Data'),
    (BAD_CLIENT_CREDENTIALS, 'Invalid Client Credentials'),
    (EXPIRED_TOKEN, 'Expired Token'),
    (PROVIDER_SERVER_ERROR, 'Provider Server Error'),
    (RESOURCE_NOT_FOUND, 'Resource not found'),
    (API_LIMIT, 'API call exceeded rate limit due to too many requests'),
    (
        MISSING_GITHUB_APP_INSTALLATION,
        'Github App is not installed on the organization',
    ),
    (PROVIDER_GRAPHQL_ERROR, 'Provider Graphql API Error'),
    (CONNECTION_TIMEOUT, 'Connection Time Out'),
    (DEFAULT_GRAPHQL_ERROR, 'Default GraphQL Error'),
    (ACCESS_REVOKED, 'Access Revoked'),
    (USER_INPUT_ERROR, 'The user entered an invalid value'),
    (GATEWAY_TIMEOUT, 'Gateway Timeout'),
    (BAD_GATEWAY, 'Bad Gateway'),
    (BAD_REQUEST, 'Bad request syntax or unsupported method'),
    (SERVICE_UNAVAILABLE, 'Service Unavailable'),
]

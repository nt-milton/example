AWS_VENDOR = 'AWS'
GCP_VENDOR = 'Google Cloud Platform'
AZURE_VENDOR = 'Microsoft Azure'
HEROKU_VENDOR = 'Heroku'
OKTA_VENDOR = 'Okta'
GITHUB_APPS = 'Github Apps'
DIGITALOCEAN = 'DigitalOcean'
REQUESTS_TIMEOUT = 120 * 3  # seconds (temporary fix)

ALREADY_EXISTS = 'already_exists'
PENDING = 'pending'
DELETING = 'deleting'
SYNC = 'sync'
SUCCESS = 'success'
ERROR = 'error'
SETUP_COMPLETE = 'setup_complete'
CONNECTION_STATUS = [
    (PENDING, 'Pending'),
    (SYNC, 'Sync'),
    (ALREADY_EXISTS, 'Already Exists'),
    (SUCCESS, 'Success'),
    (ERROR, 'Error'),
    (SETUP_COMPLETE, 'Setup Complete'),
]

PUBLIC_AUTHENTICATION_KEYS = {'checkr': ['authorized']}

# SUBSCRIPTION TYPE SELF OR SAAS
SELF_MANAGED_SUBSCRIPTION = 'SELF'

OPTIMIZED_INTEGRATIONS = ['datadog', 'jira', 'github apps']

ON_CREATE_PAYROLL_CONNECTION_ACCOUNT = 'onPayrollConnectionAccountCreated'
ACTION_ITEM_FOR_PAYROLL_INTEGRATION = '00-S-002'

from enum import Enum

CATEGORIES = [
    ('Asset Management', 'Asset Management'),
    (
        'Business Continuity & Disaster Recovery',
        'Business Continuity & Disaster Recovery',
    ),
    ('Capacity & Performance Planning', 'Capacity & Performance Planning'),
    ('Change Management', 'Change Management'),
    ('Cloud Security', 'Cloud Security'),
    ('Compliance', 'Compliance'),
    ('Configuration Management', 'Configuration Management'),
    ('Cryptographic Protections', 'Cryptographic Protections'),
    ('Data Classification & Handling', 'Data Classification & Handling'),
    ('Embedded Technology', 'Embedded Technology'),
    ('Endpoint Security', 'Endpoint Security'),
    ('Human Resources Security', 'Human Resources Security'),
    ('Identification & Authentication', 'Identification & Authentication'),
    ('Incident Response', 'Incident Response'),
    ('Information Assurance', 'Information Assurance'),
    ('Maintenance', 'Maintenance'),
    ('Mobile Device Management', 'Mobile Device Management'),
    ('Monitoring', 'Monitoring'),
    ('Network Security', 'Network Security'),
    ('Physical & Environmental Security', 'Physical & Environmental Security'),
    ('Privacy', 'Privacy'),
    ('Project & Resource Management', 'Project & Resource Management'),
    ('Risk Management', 'Risk Management'),
    ('Secure Engineering & Architecture', 'Secure Engineering & Architecture'),
    ('Security & Privacy Governance', 'Security & Privacy Governance'),
    ('Security Awareness & Training', 'Security Awareness & Training'),
    ('Security Operations', 'Security Operations'),
    ('Technology Development & Acquisition', 'Technology Development & Acquisition'),
    ('Third-Party Management', 'Third-Party Management'),
    ('Threat Management', 'Threat Management'),
    ('Vulnerability & Patch Management', 'Vulnerability & Patch Management'),
    ('Web Security', 'Web Security'),
    ('Other', 'Other'),
]

FREQUENCIES = [
    ('Not Applicable', 'Not Applicable'),
    ('Every Day', 'Every Day'),
    ('Every Week', 'Every Week'),
    ('Every Month', 'Every Month'),
]

CHOICES = [('YES', 'Yes'), ('NO', 'No'), ('N_A', 'N/A')]

ATTRIBUTES_TYPE: dict[str, str] = {
    'TEXT': 'TEXT',
    'NUMBER': 'NUMBER',
    'DATE': 'DATE',
    'USER': 'USER',
    'BOOLEAN': 'BOOLEAN',
    'SINGLE_SELECT': 'SINGLE_SELECT',
    'JSON': 'JSON',
}

COMPANY_NAME_PLACEHOLDER = 'COMPANY_NAME'
COMPANY_LOGO_PLACEHOLDER = 'COMPANY_LOGO'
SUFFIX_LOGO_PLACEHOLDER = '_LOGO'
MAX_DOWNLOAD_FILES = 10
EMPTY_STRING = ''


class WSEventTypes(Enum):
    ALERT = 'ALERT'
    LIBRARY_QUESTIONS_ADDED = 'LIBRARY_QUESTIONS_ADDED'
    LIBRARY_QUESTIONS_DELETED = 'LIBRARY_QUESTIONS_DELETED'
    LIBRARY_QUESTION_ANSWERED = 'LIBRARY_QUESTION_ANSWERED'


WS_AUDITOR_GROUP_NAME = 'audits-app-room'

DAILY = 'daily'
WEEKLY = 'weekly'

SECONDS_IN_DAY = 24 * 60 * 60
SECONDS_IN_MINUTE = 60
DAYS_IN_YEAR = 365

CONCIERGE_GROUP = 'Concierge'

AUTH_PROVIDERS = dict(OKTA='OKTA', COGNITO='COGNITO')
OKTA, COGNITO = AUTH_PROVIDERS.values()

AUTH_GROUPS = 'auth_groups'
CUSTOM_ORGANIZATION_ID_CLAIM = 'custom:organizationId'
COGNITO_USERNAME = 'cognito:username'
COGNITO_GROUPS = 'cognito:groups'
TOKEN_EMAIL_CLAIM = 'email'

REQUEST_OPERATION_KEY = 'laika_operation'

# DO NOT MESS WITH THESE UNLESS YOU KNOW WHAT YOU'RE DOING
LOCALHOST_REGEX = r'^http://localhost:[0-9]+$'
LAIKA_SUB_DOMAINS_REGEX = r'^https://[\w-]+\.heylaika\.com$'
EXCEL_PLUGIN_REGEX = r'^https:\/\/(.*)-?magic-excel-plugin\.(s3|heylaika)?(\.us-east-1)?(\.amazonaws)?\.com$'  # noqa: E501
# eol

OCTET_STREAM_CONTENT_TYPE = 'application/octet-stream'

WORD_DOCUMENT_EXTENSION = {'DOC': '.doc', 'DOCX': '.docx'}

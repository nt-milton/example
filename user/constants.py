import os

from laika.constants import ATTRIBUTES_TYPE
from laika.settings import AUDITS_BACKEND, CONCIERGE_BACKEND, LAIKA_BACKEND

LAST_NAME = 'Last Name'
FIRST_NAME = 'First Name'
LAIKA_PERMISSION = 'Laika Permission'

SUPER = 'super'
AUDITOR_ADMIN_LOWERCASE = 'auditor_admin'

MAGIC_LINK_NOT_FOUND = 'There is no link found'

MAGIC_LINK_TOKEN_EXPIRED = 'Token expired'

USER_ROLES = {
    'SUPER_ADMIN': 'SuperAdmin',
    'ADMIN': 'OrganizationAdmin',
    'CONTRIBUTOR': 'OrganizationMember',
    'VIEWER': 'OrganizationViewer',
    'SALESPERSON': 'OrganizationSales',
}

AUDITOR_ROLES = {
    'AUDITOR_ADMIN': 'AuditorAdmin',
    'AUDITOR': 'Auditor',
}

CONCIERGE_ROLES = {'CONCIERGE': 'Concierge'}

LOGIN_APP_URL = {
    'dev': 'https://login-dev.heylaika.com',
    'staging': 'https://login-staging.heylaika.com',
    'rc': 'https://login-rc.heylaika.com',
    'prod': 'https://login.heylaika.com',
}

OKTA_APPS_NAME_DEV_LOCAL = {
    f'{LAIKA_BACKEND}': ['laika_laikadev_1', 'Laika-Dev'],
    f'{AUDITS_BACKEND}': ['Audits-Dev'],
    f'{CONCIERGE_BACKEND}': ['Concierge-Dev'],
}

OKTA_APPS_NAME_STG = {
    f'{LAIKA_BACKEND}': ['laika_laikastaging_1', 'Laika-Staging'],
    f'{AUDITS_BACKEND}': ['Audits-Staging'],
    f'{CONCIERGE_BACKEND}': ['Concierge-Staging'],
}

OKTA_APPS_NAME_PROD = {
    f'{LAIKA_BACKEND}': ['laika_laika_1', 'Laika'],
    f'{AUDITS_BACKEND}': ['Audits-Production'],
    f'{CONCIERGE_BACKEND}': ['Concierge-Production'],
}

OKTA_APPS_NAMES = {
    'local': OKTA_APPS_NAME_DEV_LOCAL,
    'dev': OKTA_APPS_NAME_DEV_LOCAL,
    'staging': OKTA_APPS_NAME_STG,
    'rc': OKTA_APPS_NAME_STG,
    'prod': OKTA_APPS_NAME_PROD,
}

DEV_AND_LOCAL_GROUPS = {
    f'{LAIKA_BACKEND}': ['Laika-Dev'],
    f'{AUDITS_BACKEND}': ['Audits-Dev'],
    f'{CONCIERGE_BACKEND}': ['Concierge-Dev'],
}

OKTA_GROUPS_NAMES = {
    'local': DEV_AND_LOCAL_GROUPS,
    'dev': DEV_AND_LOCAL_GROUPS,
    'staging': {
        f'{LAIKA_BACKEND}': ['Laika-Staging'],
        f'{AUDITS_BACKEND}': ['Audits-Staging'],
        f'{CONCIERGE_BACKEND}': ['Concierge-Staging'],
    },
    'rc': {
        f'{LAIKA_BACKEND}': ['Laika-Staging'],
        f'{AUDITS_BACKEND}': ['Audits-Staging'],
        f'{CONCIERGE_BACKEND}': ['Concierge-Staging'],
    },
    'prod': {
        f'{LAIKA_BACKEND}': ['Laika-Production'],
        f'{AUDITS_BACKEND}': ['Audits-Dev'],
        f'{CONCIERGE_BACKEND}': ['Concierge-Dev'],
    },
}

OKTA_ROLES = {
    'LaikaAdmin': 'OrganizationAdmin',
    'LaikaContributor': 'OrganizationMember',
    'LaikaViewer': 'OrganizationViewer',
    'LaikaSalesperson': 'OrganizationSales',
}

USER_STATUS = {
    'ACTIVE': 'ACTIVE',
    'PENDING_INVITATION': 'PENDING_INVITATION',
    'INVITATION_EXPIRED': 'INVITATION_EXPIRED',
    'PASSWORD_EXPIRED': 'PASSWORD_EXPIRED',
    'UNKNOWN': 'UNKNOWN',
}

ALERT_PREFERENCES = {'NEVER': 'Never', 'DAILY': 'Daily', 'IMMEDIATELY': 'Immediately'}

EMAIL_PREFERENCES = {'NEVER': 'Never', 'DAILY': 'Daily', 'WEEKLY': 'Weekly'}

INVITATION_TYPES = {
    'DELEGATION': 'DELEGATION',
    'INVITATION': 'INVITATION',
}

DELEGATION_PATHS = {
    'ACTIVE': '/integrations',
    'ONBOARDING': '/onboarding/automate-compliance',
}

STATES = {'ONBOARDING': 'ONBOARDING', 'ACTIVE': 'ACTIVE'}

ONBOARDING, ACTIVE = STATES.values()

(
    ROLE_SUPER_ADMIN,
    ROLE_ADMIN,
    ROLE_MEMBER,
    ROLE_VIEWER,
    SALESPERSON,
) = USER_ROLES.values()

AUDITOR_ADMIN, AUDITOR = AUDITOR_ROLES.values()

(CONCIERGE,) = CONCIERGE_ROLES.values()

COGNITO_ROLE_GROUPS = {
    f'{LAIKA_BACKEND}': [
        ROLE_SUPER_ADMIN,
        ROLE_ADMIN,
        ROLE_MEMBER,
        ROLE_VIEWER,
        SALESPERSON,
    ],
    f'{AUDITS_BACKEND}': [AUDITOR_ADMIN, AUDITOR],
    f'{CONCIERGE_BACKEND}': [CONCIERGE],
}

USER_GROUPS = {
    ROLE_SUPER_ADMIN: 'premium_super',
    ROLE_ADMIN: 'premium_admin',
    ROLE_MEMBER: 'premium_member',
    ROLE_VIEWER: 'premium_viewer',
    SALESPERSON: 'premium_sales',
    AUDITOR_ADMIN: 'auditor_admin',
    AUDITOR: 'auditor',
    CONCIERGE: 'concierge',
}

ACTIVE_PEOPLE_SHEET_TITLE = 'Active people'
DEACTIVATED_PEOPLE_SHEET_TITLE = 'Deactivated people'

REQUIRED_USER_HEADERS = [FIRST_NAME, LAST_NAME, 'Email']
MAIN_HEADERS = [
    {
        'key': 'first_name',
        'name': FIRST_NAME,
        'width': '25',
    },
    {
        'key': 'last_name',
        'name': LAST_NAME,
        'width': '25',
    },
    {
        'key': 'email',
        'name': 'Email',
        'width': '50',
    },
]
PERMISSION_HEADERS = [
    {
        'key': 'role',
        'name': LAIKA_PERMISSION,
        'width': '25',
    }
]

EVIDENCE_HEADERS = [
    {
        'key': 'acknowledged_policies',
        'name': 'Acknowledged Policies (Completion Date)',
        'width': '40',
    },
    {
        'key': 'unacknowledged_policies',
        'name': 'Unacknowledged Policies',
        'width': '40',
    },
]

PEOPLE_HEADERS = [
    {
        'key': 'phone_number',
        'name': 'Phone Number',
        'width': '50',
    },
    {
        'key': 'title',
        'name': 'Title',
        'width': '50',
    },
    {
        'key': 'department',
        'name': 'Department',
        'width': '50',
    },
    {
        'key': 'manager_email',
        'name': 'Manager Email',
        'width': '50',
    },
    {
        'key': 'employment_type',
        'name': 'Employment Type',
        'width': '50',
    },
    {
        'key': 'employment_subtype',
        'name': 'Employment Subtype',
        'width': '50',
    },
    {
        'key': 'background_check_status',
        'name': 'Background Check Status',
        'width': '25',
    },
    {
        'key': 'background_check_passed_on',
        'name': 'Background Check Passed On',
        'width': '25',
    },
    {
        'key': 'start_date',
        'name': 'Start Date',
        'width': '25',
    },
    {
        'key': 'end_date',
        'name': 'End Date',
        'width': '25',
    },
    {
        'key': 'employment_status',
        'name': 'Employment Status',
        'width': '25',
    },
]
ALL_HEADERS = MAIN_HEADERS + PERMISSION_HEADERS + PEOPLE_HEADERS

HEADER_BULK_USERS = PERMISSION_HEADERS + MAIN_HEADERS

# User model attributes used in incredible filters
USER_ATTRIBUTES = {
    'first_name': {
        'query_path': 'first_name',
        'attribute_type': ATTRIBUTES_TYPE['TEXT'],
    },
    'last_name': {'query_path': 'last_name', 'attribute_type': ATTRIBUTES_TYPE['TEXT']},
    'email': {'query_path': 'email', 'attribute_type': ATTRIBUTES_TYPE['TEXT']},
    'phone_number': {
        'query_path': 'phone_number',
        'attribute_type': ATTRIBUTES_TYPE['TEXT'],
    },
    'title': {'query_path': 'title', 'attribute_type': ATTRIBUTES_TYPE['TEXT']},
    'manager': {
        'query_path': 'manager__email',
        'attribute_type': ATTRIBUTES_TYPE['USER'],
    },
    'department': {
        'query_path': 'department',
        'attribute_type': ATTRIBUTES_TYPE['TEXT'],
    },
    'employment_type': {
        'query_path': 'employment_type',
        'attribute_type': ATTRIBUTES_TYPE['SINGLE_SELECT'],
    },
    'employment_subtype': {
        'query_path': 'employment_subtype',
        'attribute_type': ATTRIBUTES_TYPE['SINGLE_SELECT'],
    },
    'background_check_passed_on': {
        'query_path': 'background_check_passed_on',
        'attribute_type': ATTRIBUTES_TYPE['DATE'],
    },
    'background_check_status': {
        'query_path': 'background_check_status',
        'attribute_type': ATTRIBUTES_TYPE['SINGLE_SELECT'],
    },
    'start_date': {
        'query_path': 'start_date',
        'attribute_type': ATTRIBUTES_TYPE['DATE'],
    },
    'end_date': {'query_path': 'end_date', 'attribute_type': ATTRIBUTES_TYPE['DATE']},
    'employment_status': {
        'query_path': 'employment_status',
        'attribute_type': ATTRIBUTES_TYPE['SINGLE_SELECT'],
    },
    'compliant_completed': {
        'query_path': 'compliant_completed',
        'attribute_type': ATTRIBUTES_TYPE['BOOLEAN'],
    },
    'security_training': {
        'query_path': 'security_training',
        'attribute_type': ATTRIBUTES_TYPE['BOOLEAN'],
    },
    'policies_reviewed': {
        'query_path': 'policies_reviewed',
        'attribute_type': ATTRIBUTES_TYPE['BOOLEAN'],
    },
}


INVITATION_EXPIRATION_DAYS = os.getenv('PASSWORD_EXPIRATION_DAYS') or 7
NO_DAYS_LEFT = 0

A_UNICODE = 65
INITIAL_USER_ROW = 3
DOMAIN_INDEX = -1

PASSWORD_TIMES = {
    'PASSWORD_EXPIRATION_DAYS': 90,
    'THREE_HOURS': 3 * 3600,
}

OTP_DEFAULT_LENGTH = 6

TIME_TO_CHANGE_PASS = 'three hours'

INVITATION_DAYS_TO_EXPIRE = '7'

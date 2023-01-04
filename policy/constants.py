from datetime import datetime

import pytz

from laika.constants import ATTRIBUTES_TYPE

ONBOARDING_POLICIES = [
    ('Information Security Policy', 'Information Security Policy'),
    (
        'Business Continuity and Disaster Recovery Plan',
        'Business Continuity and Disaster Recovery Plan',
    ),
    ('Compliance and Risk Management Policy', 'Compliance and Risk Management Policy'),
    (
        'Configuration and Change Management Policy',
        'Configuration and Change Management Policy',
    ),
    ('Data Protection and Handling Policy', 'Data Protection and Handling Policy'),
    ('Employee Handbook', 'Employee Handbook'),
    ('Hiring Policy', 'Hiring Policy'),
    ('Incident Response Policy', 'Incident Response Policy'),
    ('Privacy Notice Policy', 'Privacy Notice Policy'),
    ('Supplier Risk Management Policy', 'Supplier Risk Management Policy'),
]

POLICY_ATTRIBUTES = {
    'display_id': ATTRIBUTES_TYPE['NUMBER'],
    'name': ATTRIBUTES_TYPE['TEXT'],
    'description': ATTRIBUTES_TYPE['TEXT'],
    'is_published': ATTRIBUTES_TYPE['BOOLEAN'],
    'category': ATTRIBUTES_TYPE['TEXT'],
}

RELEASE_DATE_EPOCH = 1643068800

DATE = datetime.utcfromtimestamp(int(RELEASE_DATE_EPOCH))

COMPLIANCE_RELEASE_DATE = datetime(
    year=DATE.year,
    month=DATE.month,
    day=DATE.day,
    hour=DATE.hour,
    minute=DATE.minute,
    second=DATE.second,
    tzinfo=pytz.UTC,
)

INCOMPATIBLE_DRAFT_FILE_FORMAT_EXCEPTION_MSG = 'Incompatible file format'
BAD_FORMATTED_DOCX_DRAFT_FILE_EXCEPTION_MSG = 'DOCX file issue'
EMPTY_STRING = ''


PUBLISHED_POLICY_EVENT = 'PublishedPolicy'

from laika.constants import ATTRIBUTES_TYPE
from laika.types import ErrorType
from objects.system_types import (
    ACCOUNT,
    BACKGROUND_CHECK,
    CHANGE_REQUEST,
    DEVICE,
    EVENT,
    MONITOR,
    PULL_REQUEST,
    REPOSITORY,
    SERVICE_ACCOUNT,
    USER,
)
from user.models import ROLES

EVIDENCE_STATUS = (
    ('open', 'Open'),
    ('submitted', 'Submitted'),
    ('auditor_accepted', 'Auditor Accepted'),
    ('pending', 'Pending'),
)

REQUIREMENT_STATUS = (
    ('open', 'Open'),
    ('under_review', 'Under Review'),
    ('completed', 'Completed'),
)

REQUIREMENT_RESULTS = (
    ('exception_noted', 'Exception Noted'),
    ('no_exception_noted', 'No Exception Noted'),
)

COMMENTS_POOLS = (
    ('lcl', 'LCL'),
    ('all', 'All'),
    ('laika', 'Laika'),
    ('lcl-cx', 'LCL-CX'),
)

ACCOUNT_LAIKA_OBJECT_RUN_OPTIONS = (
    ('run', 'run'),
    ('skip', 'skip'),
    ('still_run', 'still_run'),
)

COMMENTS_POOLS_DICT = dict((key, value) for value, key in COMMENTS_POOLS)

LCL_POOL, ALL_POOL, LAIKA_POOL, LCL_CX_POOL = COMMENTS_POOLS_DICT.values()

SEED_FETCH_OPERATION_MAPPER = {
    'contains': 'contains',
    'does not contain': 'not_contains',
    'is': 'is',
    'is empty': 'is_empty',
    'is not empty': 'is_not_empty',
    'is before': 'is_before',
    'is after': 'is_after',
    'is between': 'is_between',
    'is not': 'is_not',
    'is any of': 'is_any_of',
    'is none of': 'is_none_of',
}

DEFAULT_PAGE = 1

DEFAULT_PAGE_SIZE = 50

roles = dict(ROLES)
ALLOW_ROLES_TO_ASSIGN_USER = [roles['SuperAdmin'], roles['OrganizationAdmin']]

EVIDENCE_ATTRIBUTES = {
    'is_laika_reviewed': {
        'query_path': 'is_laika_reviewed',
        'attribute_type': ATTRIBUTES_TYPE['BOOLEAN'],
    },
    'assignee': {
        'query_path': 'assignee__email',
        'attribute_type': ATTRIBUTES_TYPE['USER'],
    },
    'attachments_num': {
        'query_path': 'attachments_num',
        'attribute_type': ATTRIBUTES_TYPE['NUMBER'],
    },
    'evidence': {
        'query_path': 'evidence__display_id',
        'attribute_type': ATTRIBUTES_TYPE['TEXT'],
    },
    'name': {'query_path': 'name', 'attribute_type': ATTRIBUTES_TYPE['TEXT']},
    'display_id': {
        'query_path': 'display_id',
        'attribute_type': ATTRIBUTES_TYPE['TEXT'],
    },
    'requirements_count': {
        'query_path': 'requirements__display_id',
        'attribute_type': ATTRIBUTES_TYPE['TEXT'],
    },
    'reviewer': {
        'query_path': 'reviewer__user__email',
        'attribute_type': ATTRIBUTES_TYPE['USER'],
    },
    'tester': {
        'query_path': 'tester__user__email',
        'attribute_type': ATTRIBUTES_TYPE['USER'],
    },
}

POLICY_FETCH_TYPE = 'policy'
DOCUMENT_FETCH_TYPE = 'document'
TRAINING_FETCH_TYPE = 'training_log'
TEAM_FETCH_TYPE = 'team_log'
OFFICER_FETCH_TYPE = 'officer_log'
VENDOR_FETCH_TYPE = 'vendor_log'
OBJECT_FETCH_TYPE = 'object_'
MONITOR_FETCH_TYPE = 'monitor'
YEAR_MONTH_DAY_TIME_FORMAT = '%Y_%m_%d_%H_%M'
ACCOUNT_OBJECT_TYPE = 'account'
LO_SKIP_RUN = 'skip'
LO_STILL_RUN = 'still_run'
LO_RUN = 'run'


NO_EXCEPTIONS_NOTED = 'No Exceptions Noted'
NOT_TESTED = 'Not Tested'
EXCEPTION_NOTED = 'Exceptions Noted'
TEST_RESULTS = (
    ('exceptions_noted', EXCEPTION_NOTED),
    ('no_exceptions_noted', NO_EXCEPTIONS_NOTED),
    ('not_tested', NOT_TESTED),
)

VENDORS_NAME_FOR_AUDIT_REPORT = [
    'Heroku',
    'Google Cloud Platform',
    'Microsoft Azure',
    'AWS',
    'DigitalOcean',
]

CRITERIAS_TYPE = {
    'CONTROL_ENVIRONMENT': 'CC1',
    'COMMUNICATION_INFORMATION': 'CC2',
    'RISK_ASSESSMENT': 'CC3',
    'MONITORING_ACTIVITIES': 'CC4',
    'CONTROL_ACTIVITIES': 'CC5',
    'LOGICAL_PHYSICAL_ACCESS': 'CC6',
    'SYSTEM_OPERATION': 'CC7',
    'CHANGE_MANAGEMENT': 'CC8',
    'RISK_MITIGATION': 'CC9',
    'ADDITIONAL_CRITERIA_AVAILABILITY': 'A1',
    'ADDITIONAL_CRITERIA_CONFIDENTIALITY': 'C1',
    'ADDITIONAL_CRITERIA_PROCESSING_INTEGRITY': 'PI1',
    'ADDITIONAL_CRITERIA_PRIVACY': 'P1',
}

CRITERIAS_PREFFIXES = {
    'CC': 'CC',
    'A': 'A',
    'C': 'C',
    'P': 'P',
}

ER_TYPE = (('evidence_request', 'evidence_request'), ('sample_er', 'sample_er'))
ER_TYPE_DICT = dict((key, value) for value, key in ER_TYPE)
EVIDENCE_REQUEST_TYPE, SAMPLE_TYPE = ER_TYPE_DICT.values()

ER_STATUS_DICT = dict((key, value) for value, key in EVIDENCE_STATUS)

REQ_STATUS_DICT = dict((key, value) for value, key in REQUIREMENT_STATUS)


MONITOR_FILE_NAMES = [
    '[AWS] All s3 buckets are encrypted',
    '[AWS] s3 buckets are not publicly available',
    '[AWS] All DynamoDB instances are encrypted',
    '[AWS] DynamoDB instances are continuously backed up',
    '[AWS] All RDS databases are encrypted',
    '[AWS] RDS Databases are not publicly accessible',
    '[AWS] RDS cluster snapshots are encrypted',
    '[AWS] All secrets automatically rotate',
    '[AWS] CloudTrail is configured',
    '[AWS] All users have MFA enabled',
    '[Devices] All devices are encrypted',
    '[Accounts] Cloud infrastructure connected to Laika',
    '[Integration Users] All Github users have MFA',
    '[Accounts] MDM software connected to Laika',
    '[Repositories] All Repositories are private',
    '[AWS] Config is enabled',
    '[AWS] CloudWatch alarms are configured',
    '[Policies] Information Security Policy Exists in Laika',
    '[Integration Users] All users have MFA enabled',
    '[Azure] Active Directory groups have security defaults enabled',
    '[Azure] No custom subscription IAM roles exist',
    '[Azure] Storage accounts are not publicly available',
    '[Azure] Storage accounts enforce encryption in transit',
    '[Azure] Storage containers do not allow public access',
    '[Azure] Storage account denies network access by default',
    '[Azure] All storage accounts are protected by soft deletion',
    '[Azure] SQL Servers have auditing enabled',
    '[Azure] Sql Databases are encrypted by default',
    '[Test] [Integration Users] All users have MFA enabled',
    '[Accounts] MDM software connected to Laika',
    '[GCP] SQL Databases prohibit access from the open internet',
    '[GCP] Logging is configured',
    '[GCP] All secrets automatically rotate',
    '[GCP] All users have MFA enabled',
    '[GCP] Cloud monitoring is configured',
    '[GCP] All Compute Instances are using non-default service accts',
    '[GCP] All Compute Instances have explicit scopes',
    '[AWS] Strong password requirements are enforced',
    '[GCP] SQL Databases are backed up',
    '[Azure] Active Directory groups have security defaults enabled',
    '[GCP] All users have MFA enabled',
    '[GCP] All secrets automatically rotate',
    '[GCP] All Cloud Logs are Captured and Archived',
    '[GCP] Cloud SQL Database Instances Require SSL',
    '[Subtasks] No recurring tasks are overdue',
    'recurring tasks - test monitor',
    '[Azure] PostgreSQL Database Servers Enforce SSL Connections',
    '[AWS] RDS Databases are not publicly accessible',
    '[Policies] Information Security Policy Published in Laika',
    '[AWS] SNS topics are encrypted at rest',
    '[AWS] CloudTrail trail logs are encrypted with KMS CMK',
    '[AWS] Redshift cluster encryption in transit is enabled',
    'Custom Test Monitor',
    '[Azure] All storage accounts are protected by soft deletion',
    '[AWS] Log group encryption at rest should be enabled',
    '[Policies] Employee Handbook is Published',
    '[Policies] Information Security Policy Exists in Laika',
    '[AWS] All DynamoDB instances are encrypted',
    '[GCP] Cloud SQL Database Instances Require SSL',
    '[GCP] All Compute Instances use instance-specific SSH keys',
    '[AWS] RDS DB instances have Multi AZ enabled',
    '[AWS] Non-Aurora RDS DB instances have deletion protection enabled',
    '[Azure] Public network access is disabled for MySQL servers',
    '[Azure] Public network access is disabled for MySQL servers',
    '[Azure] Compute VMs have automatic updates enabled',
    '[Azure] Compute VMs have automatic updates enabled',
    '[Azure] Storage account denies network access by default',
    '[Azure] No custom subscription IAM roles exist',
    '[AWS] Auto Scaling launch config public IP should be disabled',
    '[Azure] Storage Accounts restrict network access',
    '[Azure] Storage accounts should have infrastructure encryption',
    '[AWS] No EC2 instances stopped for longer than 30 days',
    '[Azure] MySQL Servers have SSL enabled',
    '[Azure] MySQL infrastructure encryption is enabled',
    '[AWS] EC2 instances are not publicly available',
    '[AWS] EC2 instances are in VPCs',
    '[Azure] MariaDB Servers have public access disabled',
    '[AWS] EC2 Instances have detailed monitoring enabled',
    '[AWS] EBS volume encryption at rest enabled',
    '[Azure] Keyvault Vaults disallow public network access',
    '[AWS] Redshift clusters automatically upgrade major versions',
    '[Azure] keyvault soft delete enabled',
    '[AWS] Redshift clusters retain backups for at least 7 days',
    '[AWS] RDS DB automatically upgrades minor version',
    '[Azure] Keyvault Secrets have expiration set',
    '[AWS] Aurora RDS DB clusters have deletion protection enabled',
    '[Azure] Redis caches are in virtual networks',
    '[GCP] Compute Instances have shielded VM enabled',
    '[GCP] Compute Instances have confidential computing enabled',
    '[GCP] Compute Instances disable serial port connections',
    '[AWS] RDS DB instances have deletion protection enabled',
    '[AWS] RDS DB clusters have deletion protection enabled',
    '[AWS] RDS DB clusters have deletion protection enabled',
    '[AWS] Aurora RDS DB clusters have deletion protection enabled',
    '[AWS] Aurora RDS DB clusters have Multi AZ enabled',
    '[AWS] EBS volume encryption at rest enabled',
]

ADD_ATTACHMENT_INVALID_MONITOR_MESSAGE = 'Flagged monitors cannot be attached.'

LO_FILE_TYPES = [
    ACCOUNT.type.upper(),
    BACKGROUND_CHECK.type.upper(),
    DEVICE.type.upper(),
    EVENT.type.upper(),
    USER.type.upper(),
    MONITOR.type.upper(),
    PULL_REQUEST.type.upper(),
    REPOSITORY.type.upper(),
    SERVICE_ACCOUNT.type.upper(),
    CHANGE_REQUEST.type.upper(),
    'BACKGROUND_REQUEST'
    # This one was a previous one that we need to check although it doesn't
    # exist on new objects
]

ATTACH_FLAGGED_MONITORS_ERROR = ErrorType(
    code='fieldwork', message=ADD_ATTACHMENT_INVALID_MONITOR_MESSAGE
)

OTHER_SOURCE_TYPE = 'other'
OBJECT_SOURCE_TYPE = 'object'
MONITOR_SOURCE_TYPE = 'monitor'
LAIKA_WF_SOURCE_TYPE = 'laika_workflow'
LAIKA_EVIDENCE_SOURCE_TYPE = 'laika_evidence'
POLICY_SOURCE_TYPE = 'policy'


SOURCE_TYPE_MAPPER = {
    POLICY_FETCH_TYPE: POLICY_SOURCE_TYPE,
    DOCUMENT_FETCH_TYPE: LAIKA_EVIDENCE_SOURCE_TYPE,
    TRAINING_FETCH_TYPE: LAIKA_EVIDENCE_SOURCE_TYPE,
    TEAM_FETCH_TYPE: LAIKA_EVIDENCE_SOURCE_TYPE,
    OFFICER_FETCH_TYPE: LAIKA_EVIDENCE_SOURCE_TYPE,
    VENDOR_FETCH_TYPE: LAIKA_EVIDENCE_SOURCE_TYPE,
    OBJECT_FETCH_TYPE: OBJECT_SOURCE_TYPE,
    MONITOR_FETCH_TYPE: MONITOR_SOURCE_TYPE,
    OTHER_SOURCE_TYPE: OTHER_SOURCE_TYPE,
}

CHECKLIST_AUTOMATED_TESTING_SEPARATOR = '<div id="checklist-separator"></div>'

from enum import Enum

from feature.constants import (
    new_controls_feature_flag,
    read_only_playbooks_feature_flag,
)

STATUS = {'IMPLEMENTED': 'IMPLEMENTED', 'NOT IMPLEMENTED': 'NOT IMPLEMENTED'}

CONTROLS_MONITORS_HEALTH = {
    'NO_MONITORS': 'NO_MONITORS',
    'NOT_IMPLEMENTED': 'NOT_IMPLEMENTED',
    'FLAGGED': 'FLAGGED',
    'NO_DATA': 'NO_DATA',
    'HEALTHY': 'HEALTHY',
}

CONTROLS_HEALTH_FILTERS = {
    'OPERATIONAL': 'OPERATIONAL',
    'NEEDS_ATTENTION': 'NEEDS_ATTENTION',
}

MONITOR_INSTANCE_STATUS_HEALTHY = 'healthy'
MONITOR_INSTANCE_STATUS_TRIGGERED = 'triggered'
MONITOR_INSTANCE_STATUS_NO_DATASOURCE = 'no_datasource'
MAX_OWNER_LIMIT_PER_CONTROL = 3

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 10

CONTROLS_QUERIES_LOOKUP = {
    'status': 'status_uppercase__in',
    'framework': 'certification_sections__certification_id__in',
    'pillar': 'pillar_id__in',
    'tag': 'tags__id__in',
}

UNASSIGNED_OWNER_ID = '0'

CONTROL_TYPE = 'control'

CUSTOM_PREFIX = 'XX'
HIGHEST_CHAR_INDEX = 'ZZZ'
HIGHEST_NUM_INDEX = '9999'


class MetadataFields(Enum):
    TYPE = 'type'
    IS_CUSTOM = 'isCustom'
    IS_REVIEWED = 'isReviewed'
    ORGANIZATION_ID = 'organizationId'
    REQUIRED_EVIDENCE = 'requiredEvidence'
    REFERENCE_ID = 'referenceId'


REQUIRED_EVIDENCE_YES = 'Yes'
REQUIRED_EVIDENCE_NO = 'No'

COMPLETED = 'completed'
NOT_APPLICABLE = 'not_applicable'
STATUS_MAPPING = {
    COMPLETED: COMPLETED,
    NOT_APPLICABLE: NOT_APPLICABLE,
    'in_progress': 'new',
    'not_started': 'new',
}

CAPITALIZE_YES = 'Yes'

SEED_PROFILE_NAME = 'mapped-sub-tasks'
MAPPING_PROFILE_ZIP_NAME = 'mapped-sub-tasks.zip'
MAPPING_PROFILE_NAME = 'mapped-sub-tasks.xlsx'
MAPPING_SHEET = 'sub-tasks'

IN_PROGRESS = 'i'
FAILED = 'f'
DONE = 'd'

SUBTASK_TEXT = 'Sub-Task Text'
MIGRATION_ID = 'Migration ID'
LAI_REF_ID = '[LAI] Reference ID'
MAPPING_REQUIRED_FIELDS = [SUBTASK_TEXT, LAI_REF_ID]

ALL_ACTION_ITEMS = 'ALL_ACTION_ITEMS'
UNASSIGNED_ACTION_ITEMS = 'UNASSIGNED_ACTION_ITEMS'

MY_COMPLIANCE_MIGRATION_FLAGS = [
    read_only_playbooks_feature_flag,
    new_controls_feature_flag,
]

SEED_PROFILES_MAPPING = {
    'SOC 2 Security': '[MIGRATION][Playbooks → My Compliance] SOC-S',
    'SOC 2 Availability': '[MIGRATION][Playbooks → My Compliance] SOC-A',
    'SOC 2 Confidentiality': '[MIGRATION][Playbooks → My Compliance] SOC-C',
    'ISO 27001/2 (2013)': '[MIGRATION][Playbooks → My Compliance] ISO',
    'HIPAA Security': '[MIGRATION][Playbooks → My Compliance] HIPAA-S',
    'GDPR': '[MIGRATION][Playbooks to My Compliance] GDPR',
    'CCPA': '[MIGRATION][Playbooks to My Compliance] CCPA',
}

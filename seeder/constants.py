FIELDWORK_REQUIRED_EVIDENCE_FIELDS = [
    'display_id',
    'requirements',
    'short_name',
    'instructions',
]

FIELDWORK_EVIDENCE_FIELDS = [*FIELDWORK_REQUIRED_EVIDENCE_FIELDS, 'fetch_logic']

REQUIREMENT_REQUIRED_FIELDS = ['display_id', 'name', 'description']
REQUIREMENT_FIELDS = [*REQUIREMENT_REQUIRED_FIELDS, 'exclude_in_report']

FETCH_LOGIC_REQUIRED_FIELDS = ['code', 'type', 'query']

FIELDWORK_REQUIRED_CRITERIA_FIELDS = ['display_id', 'description']

FIELDWORK_CRITERIA_FIELDS = [*FIELDWORK_REQUIRED_CRITERIA_FIELDS, 'requirements']

FETCH_LOGIC_FIELDS = [*FETCH_LOGIC_REQUIRED_FIELDS, 'description']

PENDING = 'p'
IN_PROGRESS = 'i'
FAILED = 'f'
DONE = 'd'
UPDATING = 'u'

SEED_STATUS = (
    (PENDING, 'Pending'),
    (IN_PROGRESS, 'In Progress'),
    (FAILED, 'Failed'),
    (DONE, 'Done'),
    (UPDATING, 'Updating'),
)

ALL_MY_COMPLIANCE_ORGS = 'My Compliance Organizations Upsert'
ALL_MY_COMPLIANCE_ORG_FAKE_WEBSITE = 'https://fake.org'
ALL_MY_COMPLIANCE_ORG_FAKE_SFDC_ID = 'fakeId'

SEED_EMAIL_TEMPLATE = 'organization_seed_created.html'

CX_APP_ROOM = 'cx-app'

FIELDWORK_REQUIRED_TEST_FIELDS = ['display_id', 'requirement', 'name', 'checklist']

FIELDWORK_TEST_FIELDS = [*FIELDWORK_REQUIRED_TEST_FIELDS, 'result', 'notes']


POPULATION_REQUIRED_FIELDS = ['display_id', 'name', 'instructions', 'evidence_requests']

POPULATION_FIELDS = [
    *POPULATION_REQUIRED_FIELDS,
    'default_source',
    'sample_logic',
    'sample_size',
    'manual_configuration',
    'laika_source_configuration',
]

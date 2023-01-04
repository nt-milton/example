CONTROL_FAMILY_AIRTABLE_NAME = 'Control Families (Pillars)'
CONTROL_FAMILY_REFERENCES = 'Control Families (references)'
GROUPS_AIRTABLE_NAME = 'Groups'
ACTION_ITEMS_AIRTABLE_NAME = 'Action Items'
TAGS_AIRTABLE_NAME = 'Tags'
OFFICERS_AIRTABLE_NAME = 'Officers'
TEAMS_AIRTABLE_NAME = 'Teams (Charters)'
QUESTIONS_AIRTABLE_NAME = 'Questions'
OBJECT_AIRTABLE_NAME = 'Object Types'
OBJECT_ATTRIBUTES_AIRTABLE_NAME = 'Object Type Attributes'
CHECKLIST_AIRTABLE_NAME = 'Checklist'
TRAINING_AIRTABLE_NAME = 'Files'
GUIDES_AIRTABLE_NAME = 'Implementation Guides'
EVIDENCE_METADATA_AIRTABLE_NAME = 'Evidence Metadata'

NAME = 'Name'
REFERENCE_ID = 'Reference ID'
HOUSEHOLD = 'Household'
FRAMEWORK_TAG = 'Framework Tag'
SUGGESTED_OWNER = 'Suggested Owner'
ROLES = 'Roles'
SORT_ORDER = 'Sort Order'
SORT_ORDER_WITHIN_GROUP = 'Sort Order (within Group)'
DESCRIPTION = 'Description'
CHARTER = 'Charter'
LAST_MODIFIED = 'Last Modified'
CONTROL_REFERENCE_ID = 'Control Reference ID (via Linked Controls)'
ACRONYM = 'Acronym'
FRAMEWORKS = 'Frameworks'
CERTIFICATION_SECTION = 'Certification Section'
STATUS = 'Status'
GROUP_REFERENCE_ID = 'Group Reference ID'
CHECKLIST = 'Checklist'
TYPE = 'Type'
CATEGORY = 'Category'
FILE_ATTACHMENT = 'File Attachment'
IS_SYSTEM_TYPE = 'Is System Type'
DISPLAY_INDEX = 'Display Index'
ICON = 'Icon'
COLOR = 'Color'
TYPE_NAME = 'Type Name'
ATTRIBUTE_TYPE = 'Attribute Type'
MIN_WIDTH = 'Min Width'
IS_PROTECTED = 'Is Protected'
IS_REQUIRED = 'Is Required'
RECURRENT_SCHEDULE = 'Recurrent Schedule'
REQUIRES_EVIDENCE = 'Requires Evidence'
DEFAULT_VALUE = 'Default Value'
SELECT_OPTIONS = 'Options'
QUESTIONNAIRE = 'Questionnaire'
QUESTION_TEXT = 'Question Text'
ANSWER = 'Answer'
SHORT_ANSWER = 'Short Answer'
SHORT_ANSWER_OPTIONS = 'Short Answer Options'
TECHNICAL = 'Technical'
HUMAN_RESOURCES = 'Human Resources'
COMPLIANCE = 'Compliance'
CONTENT_STATUS = 'Content Status'
ATTACHMENT = 'Attachment'

FRAMEWORK_NAME = 'Framework Name'
SECTION_NAMES = 'Core Controls Framework Reference'
AIRTABLE_RECORD_ID = 'airtable_record_id'
CERTIFICATION_SECTION_NAME = 'Certification Section'
RESPONSE_REDIRECT_PATH = '../'
SYNC_PATH = 'sync_from_airtable/'
BLUEPRINT_FORMULA = {'Content Status': 'Final (Approved)'}
TRAINING_BLUEPRINT_FORMULA = {**BLUEPRINT_FORMULA, 'Policy Type': 'Training'}

ISO_FORMAT = '%Y-%m-%dT%H:%M:%S.%f%z'

CONTROL_FAMILY_REQUIRED_FIELDS = [NAME, ACRONYM]
CONTROL_REQUIRED_FIELDS = [
    NAME,
    REFERENCE_ID,
    CONTROL_FAMILY_REFERENCES,
    HOUSEHOLD,
    FRAMEWORK_TAG,
]

GROUP_REQUIRED_FIELDS = [NAME, REFERENCE_ID, SORT_ORDER]
FRAMEWORK_REQUIRED_FIELDS = [FRAMEWORK_NAME, SECTION_NAMES]
SECTIONS_REQUIRED_FIELDS = [CERTIFICATION_SECTION, FRAMEWORKS]
TAG_REQUIRED_FIELDS = [NAME]
OFFICERS_REQUIRED_FIELDS = [NAME, DESCRIPTION]
OBJECT_REQUIRED_FIELDS = [NAME, DISPLAY_INDEX, TYPE, ICON, COLOR, DESCRIPTION]
OBJECT_ATTRIBUTE_REQUIRED_FIELDS = [
    TYPE_NAME,
    NAME,
    DISPLAY_INDEX,
    ATTRIBUTE_TYPE,
    MIN_WIDTH,
]
TEAMS_REQUIRED_FIELDS = [NAME, DESCRIPTION, CHARTER]
QUESTIONS_REQUIRED_FIELDS = [QUESTIONNAIRE, QUESTION_TEXT, ANSWER]
CHECKLIST_REQUIRED_FIELDS = [CHECKLIST, DESCRIPTION, TYPE, CATEGORY]
GUIDES_REQUIRED_FIELDS = [NAME, DESCRIPTION]
TRAINING_REQUIRED_FIELDS = [NAME, CATEGORY, DESCRIPTION, FILE_ATTACHMENT]
ACTION_ITEM_REQUIRED_FIELDS = [REFERENCE_ID, NAME, DESCRIPTION, CONTROL_REFERENCE_ID]
EVIDENCE_METADATA_REQUIRED_FIELDS = [REFERENCE_ID]

STATUS_PRESCRIBED = 'prescribed'
STATUS_NOT_PRESCRIBED = 'not_prescribed'

OBJECT_COLORS = {
    'purpleTint80': '#8572C5',
    'accentGreen01': '#7CBA8A',
    'accentGreen03': '#33AB77',
    'brandViolet': '#3B2552',
    'aquaTint80': '#81CCD8',
    'greenTint80': '#95C7A1',
    'accentRed': '#D00000',
    'accentOrange': '#F3670F',
    'brandColorB': '#7AACDE',
    'yellowTint50': '#FCDA84',
    'orangeTint50': '#F9B387',
}

RANDOM_BACKGROUNDS = [
    '#61BFCE',
    '#F3670F',
    '#F9B60A',
    '#33AB77',
    '#F4843E',
    '#95C7A1',
    '#2B579A',
    '#009DFF',
    '#D00000',
    '#F9C43A',
    '#D24726',
    '#217346',
    '#664FB7',
    '#1E3C57',
    '#3B2552',
    '#7AACDE',
]

TL_SECTION_START = (
    '<div style="'
    'display:flex;'
    'flex-wrap: wrap;'
    'width: 350px;'
    'max-height: 150px;'
    'overflow-y: auto;">'
)

TL_SECTION_END = '</div>'

RECT_DIV_START = (
    '<div style="'
    'margin-right: 8px;'
    'margin-bottom: 4px;'
    'background: {random_color};'
    'color: #222;'
    'padding: 4px 6px;'
    'font-size: 12px;'
    'width: max-content;'
    'text-align: center;">'
)

CHIP_DIV_START = (
    '<div style="'
    'margin-right: 8px;'
    'margin-bottom: 4px;'
    'background: {random_color};'
    'color: #222;'
    'padding: 4px 6px;'
    'border-radius: 24px;'
    'font-size: 12px;'
    'font-weight: 500;'
    'width: max-content;'
    'text-align: center;">'
)
CHIP_DIV_END = '</div>'

SECTION_CHIP_DIV_START = (
    '<div style="'
    'margin-right: 8px;'
    'margin-bottom: 4px;'
    'background: {random_color};'
    'color: #222;'
    'padding: 4px;'
    'border-radius: 4px;'
    'font-size: 12px;'
    'width: max-content;'
    'text-align: center;">'
)

ANCHOR = '<a href="'
ANCHOR_END = '</a>'

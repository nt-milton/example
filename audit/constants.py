DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 12

AUDIT_FIRMS = ['Laika Compliance', 'Test Audit Firm']

SOC_2_TYPE_1 = 'SOC 2 Type 1'
SOC_2_TYPE_2 = 'SOC 2 Type 2'


AUDIT_TYPES = [SOC_2_TYPE_1, SOC_2_TYPE_2]

AUDIT_FRAMEWORK_TYPES = [
    ('SOC_2_TYPE_1', 'SOC 2 Type 1'),
    ('SOC_2_TYPE_2', 'SOC 2 Type 2'),
    ('SOC_1_TYPE_1', 'SOC 1 Type 1'),
    ('SOC_1_TYPE_2', 'SOC 1 Type 2'),
    ('HITRUST', 'HITRUST'),
]

AUDIT_FRAMEWORK_TYPES_DICT = dict((key, value) for value, key in AUDIT_FRAMEWORK_TYPES)

TRUSTED_CATEGORIES = [
    'Security',
    'Availability',
    'Privacy',
    'Confidentiality',
    'Process Integrity',
]

CURRENT_AUDIT_STATUS = {
    'REQUESTED': 'requested',
    'INITIATED': 'initiated',
    'FIELDWORK': 'fieldwork',
    'IN_DRAFT_REPORT': 'draftReport',
    'COMPLETED': 'completed',
}

AUDIT_STATUS_DEPENDENCIES = {
    'INITIATED': [
        'confirm_audit_details',
        'engagement_letter_link',
        'control_design_assessment_link',
        'kickoff_meeting_link',
    ],
    'FIELDWORK': [
        'confirm_engagement_letter_signed',
        'confirm_control_design_assessment',
        'confirm_kickoff_meeting',
    ],
    'IN_DRAFT_REPORT': [
        'representation_letter_link',
        'management_assertion_link',
        'subsequent_events_questionnaire_link',
        'draft_report',
    ],
    'COMPLETED': ['confirm_completion_of_signed_documents', 'final_report'],
}

AUDIT_STATUS_ALERTS = {
    'requested': 'AUDIT_REQUESTED',
    'initiated': 'AUDIT_INITIATED',
    'fieldwork': 'FIELDWORK_INITIATED',
    'draftReport': 'DRAFT_REPORT_AVAILABLE',
    'completed': 'AUDIT_COMPLETE',
}

INITIATED_STAGE_CHECKS = [
    'engagement_letter_checked',
    'control_design_assessment_checked',
    'kickoff_meeting_checked',
]

DRAFT_REPORT_STAGE_CHECKS = [
    'review_draft_report_checked',
    'representation_letter_checked',
    'management_assertion_checked',
    'subsequent_events_questionnaire_checked',
]

TITLE_ROLES = (
    ('lead_auditor', 'Lead Auditor'),
    ('tester', 'Tester'),
    ('reviewer', 'Reviewer'),
)
TITLE_ROLES_DICT = dict((key, value) for value, key in TITLE_ROLES)

LEAD_AUDITOR_KEY = 'lead_auditor'
REVIEWER_AUDITOR_KEY = 'reviewer'
TESTER_AUDITOR_KEY = 'tester'
REVIEWERS_AUDITORS_KEY = [LEAD_AUDITOR_KEY, REVIEWER_AUDITOR_KEY]


AUDITOR_ROLES = {'auditorAdmin': 'AuditorAdmin', 'auditor': 'Auditor'}

AUDIT_STATUS_STEPS_FIELDS = {
    'DRAFT_REPORT_GENERATED': 'draft_report_generated',
    'DRAFT_REPORT_CHECKED': 'review_draft_report_checked',
}

AUDIT_STATUS_TRACK_UPDATED_FIELDS = ['draft_report']

IN_APP_DRAFT_REPORTING_FEATURE_FLAG = 'inAppDraftReportingFeatureFlag'
LAIKA_SOURCE_POPULATION_AND_SAMPLES_FEATURE_FLAG = 'laikaSourcePopSamFeatureFlag'

DRAFT_REPORT_SECTIONS = [
    ('section_1', 'Section 1'),
    ('section_2', 'Section 2'),
    ('section_3', 'Section 3'),
    ('section_4', 'Section 4'),
    ('section_5', 'Section 5'),
]
DRAFT_REPORT_SECTIONS_DICT = dict((key, value) for value, key in DRAFT_REPORT_SECTIONS)
(
    SECTION_1,
    SECTION_2,
    SECTION_3,
    SECTION_4,
    SECTION_5,
) = DRAFT_REPORT_SECTIONS_DICT.values()

HTML_INIT_CODE = '''
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <style type="text/css" media="screen,print">
        .pb_before {
            page-break-before: always !important;
        }

        .pb_after {
            page-break-after: always !important;
        }
        thead {
            display: table-row-group;
        }
        tfoot {
            display: table-row-group;
        }
        body {
            font-family: Arial !important;
            line-height: 1.63 !important;
        }
        tr, td, th, tbody, thead, tfoot {
            page-break-inside: avoid !important;
        }
    </style>
    <title>Draft Report</title>
  </head>
  <body>
'''
HTML_END_CODE = '''
  </body>
</html>
'''

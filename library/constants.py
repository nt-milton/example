from enum import Enum

from laika.constants import CATEGORIES
from laika.utils.schema_builder.types.base_field import SchemaType
from laika.utils.schema_builder.types.single_select_field import SingleSelectField
from laika.utils.schema_builder.types.text_field import TextFieldType


class FetchType(Enum):
    EXACT = 'exact_match'
    FUZZY = 'fuzzy'


STATUS_IN_PROGRESS = 'in_progress'
STATUS_NO_ANSWER = 'no_answer'
STATUS_DRAFT = 'draft'
STATUS_COMPLETED = 'completed'

NOT_ASSIGNED_USER_ID = '0'

POLICY_WEIGHT = 0.5
POLICY_TITLE_WEIGHT = 0.7
QUESTION_WEIGHT = 1.0
ANSWER_TEXT_WEIGHT = 0.8

LIBRARY_SHORT_ANSWER_TYPE = 'shortAnswer'
LIBRARY_ANSWER_TYPE = 'answer'

LibraryTemplateSchema = SchemaType(
    sheet_name='Library',
    header_title='Library',
    fields=[
        TextFieldType(name='Question', required=True),
        SingleSelectField(
            name='Category',
            required=False,
            options=[category[1] for category in CATEGORIES],
        ),
        TextFieldType(name='Answer', required=True),
        TextFieldType(name='Short Answer', required=False),
    ],
)

NOT_RAN = 'not_ran'
NO_RESULT = 'no_result'
RESULT_FOUND = 'result_found'
RESULT_FOUND_UPDATED = 'result_found_updated'

FETCH_STATUS = (
    (NOT_RAN, 'Not Ran'),
    (NO_RESULT, 'No Result'),
    (RESULT_FOUND, 'Result Found'),
    (RESULT_FOUND_UPDATED, 'Result Found, updated by user'),
)

TASK_DEFAULT_STATUS = 'not_started'
TASK_IN_PROGRESS_STATUS = 'in_progress'
TASK_ERROR_STATUS = 'error'
TASK_COMPLETED_STATUS = 'completed'

TASK_STATUS = [
    (TASK_DEFAULT_STATUS, 'Not Started'),
    (TASK_IN_PROGRESS_STATUS, 'In Progress'),
    (TASK_ERROR_STATUS, 'Error'),
    (TASK_COMPLETED_STATUS, 'Completed'),
]

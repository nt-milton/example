from laika.types import ErrorType

CANNOT_CREATE_ORGANIZATION = 'Cannot create organization'
CANNOT_GET_ORGANIZATION = 'Cannot get organization'
CANNOT_GET_ORGANIZATION_BY_ID = 'Cannot get organization by id'
CANNOT_UDPATE_ORGANIZATION = 'Cannot update organization'
CANNOT_UDPATE_ORGANIZATION_SETUP = 'Cannot update organization onboarding'
CANNOT_UDPATE_ONBOARDING_COMPLETION = 'Cannot update onboarding step completion status'
CANNOT_MOVE_ORG_OUT_OF_ONBOARDING = 'Cannot move organization out of onboarding'
MISSING_REQUIRED_FIELDS = 'Missing required fields'
CANNOT_GET_ORGANIZATION_SUMMARY = 'Cannot get organization summary'
ORGANIZATION_NOT_FOUND = 'Organization not found'
ACCESS_DENIED = 'You have no permission to create or update organization'
CANNOT_CREATE_ORGANIZATION_CHECK_IN = 'Cannot create organization checkin'
CANNOT_DELETE_ORGANIZATION_CHECK_IN = 'Cannot delete organization checkin'

CODE = 'organization'

CREATE_ORG_ERROR = ErrorType(code=CODE, message=CANNOT_CREATE_ORGANIZATION)
GET_ORG_ERROR = ErrorType(code=CODE, message=CANNOT_GET_ORGANIZATION)
UPDATE_ORG_ERROR = ErrorType(code=CODE, message=CANNOT_UDPATE_ORGANIZATION)
UPDATE_ORG_SETUP_ERROR = ErrorType(code=CODE, message=CANNOT_UDPATE_ORGANIZATION_SETUP)
UPDATE_ORG_ONBOARDING_STEP_COMPLETION_ERROR = ErrorType(
    code=CODE, message=CANNOT_UDPATE_ONBOARDING_COMPLETION
)
MOVE_ORG_OUT_OF_ONBOARDING_ERROR = ErrorType(
    code=CODE, message=CANNOT_MOVE_ORG_OUT_OF_ONBOARDING
)
GET_ORG_SUMMARY_ERROR = ErrorType(code=CODE, message=CANNOT_GET_ORGANIZATION_SUMMARY)
CREATE_ORG_CHECKIN_ERROR = ErrorType(
    code=CODE, message=CANNOT_CREATE_ORGANIZATION_CHECK_IN
)
DELETE_ORG_CHECKIN_ERROR = ErrorType(
    code=CODE, message=CANNOT_DELETE_ORGANIZATION_CHECK_IN
)

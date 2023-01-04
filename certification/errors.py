from laika.types import ErrorType

CANNOT_UNLOCK_CERTIFICATION = 'Cannot unlock certification'
CERTIFICATION_IS_ALREADY_UNLOCK = 'Certification is already unlock'

CODE = 'certification'

UPDATE_UNLOCK_CERTIFICATION_ERROR = ErrorType(
    code=CODE, message=CANNOT_UNLOCK_CERTIFICATION
)

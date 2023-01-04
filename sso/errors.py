from laika.types import ErrorType

CANNOT_CREATE_IDP = 'Cannot create identity provider in Okta'
CANNOT_GET_IDP = 'Cannot get identity provider from Okta'
CANNOT_GET_IDP_KEY = 'Cannot get identity provider key from Okta'
CANNOT_UPDATE_IDP = 'Cannot update identity provider in Okta'
INVALID_IDP = 'Requested identity provider doesn\'t exist'

CODE = 'sso'

CREATE_IDP_ERROR = ErrorType(code=CODE, message=CANNOT_CREATE_IDP)

GET_IDP_ERROR = ErrorType(code=CODE, message=CANNOT_GET_IDP)

GET_IDP_KEY_ERROR = ErrorType(code=CODE, message=CANNOT_GET_IDP_KEY)

INVALID_IDP_ERROR = ErrorType(code=CODE, message=INVALID_IDP)

UPDATE_IDP_ERROR = ErrorType(code=CODE, message=CANNOT_UPDATE_IDP)

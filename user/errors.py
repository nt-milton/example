from laika.types import ErrorType

CANNOT_INVITE_USER = 'Cannot invite user'
ACCESS_DENIED = 'You have no permission to invite or update a user'
NO_ORGANIZATION_USER = '''The user is not an admin in the
    organization it is trying to invite'''
USER_EXISTS = 'Another user exists with the same email address'
CANNOT_REMOVE_USER = 'Cannot remove user'
CANNOT_GET_USERS = 'Cannot get users'
MISSING_REQUIRED_FIELDS = 'Some required fields are missing'
CANNOT_UPDATE_USER = 'Cannot update user'
CANNOT_UPDATE_PREFERENCES = 'Cannot update preferences'
CANNOT_DELEGATE_USER_INTEGRATION = 'Cannot delegate user integration'
CANNOT_DELEGATE_UNINVITED_USER_INTEGRATION = (
    'Cannot delegate an uninvited user integration'
)
INVALID_OPERATION = '''Please use UpdateUserPreferences
    mutation to update user preferences'''

CREATE_INVITE_USER_ERROR = ErrorType(code='user', message=CANNOT_INVITE_USER)

CREATE_REMOVE_USER_ERROR = ErrorType(code='user', message=CANNOT_REMOVE_USER)

CREATE_GET_USERS_ERROR = ErrorType(code='user', message=CANNOT_GET_USERS)

CREATE_UPDATE_USER_ERROR = ErrorType(code='user', message=CANNOT_UPDATE_USER)

class EdaBaseException(Exception):
    "Base exception for edas architecture"
    pass


class EdaErrorException(EdaBaseException):
    "Exception that logs an error when raised"
    pass


class EdaWarningException(EdaBaseException):
    "Exception that logs an warning when raised"
    pass

from typing import Dict, Union

import integration.error_codes as error_codes


class ConnectionAccountSyncing(Exception):
    """Intended to be used when an integration gets deleted,
    if the connection account status is SYNC cant be deleted."""

    pass


class ConnectionAlreadyExists(Exception):
    """Intended to be used when executing an integration,
    if It realizes It is a duplicate of another active connection."""

    pass


class TooManyRequests(Exception):
    """Intended to be used when executing an integration,
    if the request response is 429(Too Many Requests) this will be raised
    to be able to handle rate limit on our different integrations."""

    pass


class TimeoutException(Exception):
    """Intended to be used when executing an integration,
    if the request response is 408(Request Timeout) this will be raised
    """

    pass


class GatewayTimeoutException(Exception):
    """Intended to be used when executing an integration,
    if the request response is 504(Gateway Timeout) this will be raised
    """

    pass


class BadGatewayException(Exception):
    """Intended to be used when executing an integration,
    if the request response is 502(Bad Gateway) this will be raised
    """

    pass


class ServiceUnavailableException(Exception):
    """Intended to be used when executing an integration,
    if the request response is 503(Service Unavailable) this will be raised
    """

    pass


class RedisError(Exception):
    """Intended to be used when a connection account cleanup
    failed due to redis connection issues."""

    pass


class ConfigurationError(Exception):
    """Intended to map all the possible errors
    that an integration can generate."""

    def __init__(
        self,
        error_code: str,
        error_message: Union[str, None] = None,
        error_response: Union[Dict, None] = None,
        is_user_input_error: bool = False,
    ):
        if error_response is None:
            error_response = {}
        self.error_code = error_code
        self.error_message = error_message
        self.error_response = error_response
        self.is_user_input_error: bool = is_user_input_error

    def __str__(self):
        return self.error_message

    @staticmethod
    def insufficient_permission(response=None):
        if response is None:
            response = {}
        error_message = 'The connection does not have admin privileges.'

        return ConfigurationError(
            error_code=error_codes.INSUFFICIENT_PERMISSIONS,
            error_message=error_message,
            error_response=response,
        )

    @staticmethod
    def denial_of_consent():
        error_message = 'The connection request was denied by the user.'

        return ConfigurationError(
            error_code=error_codes.DENIAL_OF_CONSENT, error_message=error_message
        )

    @staticmethod
    def missing_github_organization():
        error_message = 'There is no Github organization for this connection account.'

        return ConfigurationError(
            error_code=error_codes.MISSING_GITHUB_ORGANIZATION,
            error_message=error_message,
        )

    @staticmethod
    def insufficient_config_data():
        error_message = (
            'The payload for this connection is missing '
            'data required to apply the settings.'
        )

        return ConfigurationError(
            error_code=error_codes.INSUFFICIENT_CONFIG_DATA, error_message=error_message
        )

    @staticmethod
    def bad_client_credentials(response=None):
        if response is None:
            response = {}
        return ConfigurationError(
            error_code=error_codes.BAD_CLIENT_CREDENTIALS,
            error_message='The client credentials provided by the user are invalid.',
            error_response=response,
        )

    @staticmethod
    def bad_github_organization_installation(organization, response=None):
        message = (
            f"The organization: {organization} does not have the Github app installed."
        )
        if response is None:
            response = {'error': message}

        return ConfigurationError(
            error_code=error_codes.MISSING_GITHUB_APP_INSTALLATION,
            error_message=message,
            error_response=response,
        )

    @staticmethod
    def provider_server_error(error_response: Union[Dict, None] = None):
        if error_response is None:
            error_response = {}
        return ConfigurationError(
            error_code=error_codes.PROVIDER_SERVER_ERROR,
            error_message=error_response.get('message'),
            error_response=error_response,
        )

    @staticmethod
    def other_error(error_response: Union[Dict, None] = None):
        if error_response is None:
            error_response = {}
        return ConfigurationError(
            error_code=error_codes.OTHER,
            error_message='Other error',
            error_response=error_response,
        )

    @staticmethod
    def not_found(error_response: Union[Dict, None] = None):
        if error_response is None:
            error_response = {}

        return ConfigurationError(
            error_code=error_codes.RESOURCE_NOT_FOUND,
            error_message='Resource Not Found',
            error_response=error_response,
        )

    @staticmethod
    def api_limit(error_response: Union[Dict, None] = None):
        if error_response is None:
            error_response = {}

        return ConfigurationError(
            error_code=error_codes.API_LIMIT,
            error_message='API calls exceeded',
            error_response=error_response,
        )


class ConnectionResult(ConfigurationError):
    def __init__(
        self,
        status_code: str = '200',
        error_code: str = '000',
        error_message: str = '',
        error_response: Union[Dict, None] = None,
    ):
        if error_response is None:
            error_response = {}

        self.status_code = status_code
        super().__init__(error_code, error_message, error_response)

    def is_success(self):
        return (
            self.status_code == '200'
            or self.status_code == '201'
            or self.status_code == '206'
        )

    def with_error(self):
        return not self.is_success()

    def get_connection_result(self):
        return self


# Class to handle the error response received from providers
class ErrorResponse:
    def __init__(
        self, status=None, reason=None, response=None, expiration=False, headers=None
    ):
        self.status = status
        self.reason = reason
        self.response = response
        self.expiration = expiration
        self.headers = headers

    def get_reason(self):
        if self.reason is None or self.reason == '':
            self.reason = 'No reason in response'

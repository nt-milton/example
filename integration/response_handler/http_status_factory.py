import logging
import typing
from http import HTTPStatus
from typing import Any, Callable

from integration import error_codes
from integration.exceptions import (
    BadGatewayException,
    ConnectionResult,
    GatewayTimeoutException,
    ServiceUnavailableException,
    TimeoutException,
    TooManyRequests,
)
from integration.log_utils import connection_context

logger = logging.getLogger(__name__)

SERVER_ERROR = 'SERVER_ERROR'
SERVICE_UNAVAILABLE = 'SERVICE_UNAVAILABLE'


def http_errors_factory() -> dict[int, Callable[[Any, Any], Any]]:
    http_errors_dict: dict[int, Callable[[Any, Any], Any]] = {
        HTTPStatus.BAD_REQUEST: _bad_request_error_result,
        HTTPStatus.BAD_GATEWAY: _bad_gateway,
        HTTPStatus.FORBIDDEN: _forbidden_error_result,
        HTTPStatus.GATEWAY_TIMEOUT: _gateway_timeout,
        HTTPStatus.INTERNAL_SERVER_ERROR: _internal_server_error,
        HTTPStatus.NOT_FOUND: _not_found_error_result,
        HTTPStatus.REQUEST_TIMEOUT: _request_timeout_error_result,
        HTTPStatus.SERVICE_UNAVAILABLE: _service_unavailable,
        HTTPStatus.TOO_MANY_REQUESTS: _too_many_request_result,
        HTTPStatus.UNAUTHORIZED: _unauthorized_error_result,
        HTTPStatus.UNPROCESSABLE_ENTITY: _unprocessable_entity_error_result,
    }
    return http_errors_dict


def get_http_error_messages(error_code: str) -> Any:
    error_messages: dict[str, Any] = {
        error_codes.CONNECTION_TIMEOUT: (
            'The request was well-formed but the server '
            'did not receive a complete request message '
            'within the time that it was prepared to wait.'
        ),
        error_codes.BAD_CLIENT_CREDENTIALS: 'Invalid authentication credentials',
        error_codes.API_LIMIT: 'Too Many Requests',
        error_codes.RESOURCE_NOT_FOUND: 'Resource you have specified cannot be found.',
        error_codes.INSUFFICIENT_PERMISSIONS: (
            'The connection does not have admin privileges.'
        ),
        error_codes.EXPIRED_TOKEN: (
            'The token or account provided has expired or expired credentials'
        ),
        error_codes.BAD_REQUEST: 'Bad request syntax or unsupported method',
        error_codes.PROVIDER_SERVER_ERROR: {
            SERVER_ERROR: "There was a problem on vendor's end.",
            SERVICE_UNAVAILABLE: "Vendor's service unavailable.",
        },
        error_codes.GATEWAY_TIMEOUT: (
            "Vendor's gateway server did not get a response in time."
        ),
        error_codes.BAD_GATEWAY: "Invalid response received from Vendor's server",
    }

    return error_messages.get(
        error_code, f'message for error code {error_code} not found'
    )


# HTTPS ERRORS 4XX
def _request_timeout_error_result(error_response, result):
    result.error_code = error_codes.CONNECTION_TIMEOUT
    result.error_message = get_http_error_messages(error_codes.CONNECTION_TIMEOUT)
    result.error_response = error_response.response
    raise TimeoutException('Timeout Error.')


def _unprocessable_entity_error_result(error_response, result):
    result.error_code = error_codes.BAD_CLIENT_CREDENTIALS
    result.error_message = get_http_error_messages(error_codes.BAD_CLIENT_CREDENTIALS)
    result.error_response = error_response.response


def _too_many_request_result(error_response, result):
    logger.info('Too many requests, starting retry process...')
    result.error_code = error_codes.API_LIMIT
    result.error_message = get_http_error_messages(error_codes.API_LIMIT)
    result.error_response = error_response.response
    exception_message = (
        error_response.headers if error_response.headers else result.error_message
    )
    raise TooManyRequests(exception_message)


def _not_found_error_result(error_response, result):
    result.error_code = error_codes.RESOURCE_NOT_FOUND
    result.error_message = get_http_error_messages(error_codes.RESOURCE_NOT_FOUND)
    validate_vendor_message_with_revoked_access(result)
    result.error_response = error_response.response


def _forbidden_error_result(error_response, result):
    result.error_code = error_codes.INSUFFICIENT_PERMISSIONS
    result.error_message = get_http_error_messages(error_codes.INSUFFICIENT_PERMISSIONS)
    result.error_response = error_response.response
    validate_vendor_message_with_revoked_access(result)


def _unauthorized_error_result(error_response, result):
    if error_response.expiration:
        result.error_code = error_codes.EXPIRED_TOKEN
        result.error_message = get_http_error_messages(error_codes.EXPIRED_TOKEN)
    else:
        result.error_code = error_codes.BAD_CLIENT_CREDENTIALS
        result.error_message = get_http_error_messages(
            error_codes.BAD_CLIENT_CREDENTIALS
        )
    result.error_response = error_response.response


def _bad_request_error_result(error_response, result):
    result.error_code = error_codes.BAD_REQUEST
    result.error_message = get_http_error_messages(error_codes.BAD_REQUEST)
    result.error_response = error_response.response
    validate_vendor_message_with_revoked_access(result)


# HTTPS ERRORS 5XX
def _internal_server_error(error_response, result):
    result.error_code = error_codes.PROVIDER_SERVER_ERROR
    result.error_message = get_http_error_messages(
        error_codes.PROVIDER_SERVER_ERROR
    ).get(SERVER_ERROR)
    result.error_response = error_response.response


def _service_unavailable(error_response, result):
    result.error_code = error_codes.PROVIDER_SERVER_ERROR
    result.error_message = get_http_error_messages(
        error_codes.PROVIDER_SERVER_ERROR
    ).get(SERVICE_UNAVAILABLE)
    result.error_response = error_response.response
    raise ServiceUnavailableException('Service Unavailable')


def _gateway_timeout(error_response, result):
    result.error_message = get_http_error_messages(error_codes.GATEWAY_TIMEOUT)
    result.error_code = error_codes.GATEWAY_TIMEOUT
    result.error_response = error_response.response
    raise GatewayTimeoutException('Gateway Timeout')


def _bad_gateway(error_response, result):
    result.error_code = error_codes.BAD_GATEWAY
    result.error_message = get_http_error_messages(error_codes.BAD_GATEWAY)
    result.error_response = error_response.response
    raise BadGatewayException('Bad Gateway')


# THE ACCESS REVOKED MESSAGE IS DIFFERENT IN THE VENDORS
# IT MUST BE VALIDATED WITH THE ERROR MESSAGE
@typing.no_type_check
def validate_vendor_message_with_revoked_access(result: ConnectionResult):
    if connection_context.get():
        vendor_name: str = connection_context.get().connection.integration.vendor.name
        message_by_vendor: dict = {'ASANA': _asana_revoked_access(result)}
        return message_by_vendor.get(vendor_name.upper(), {})

    return 'Vendor not found to show an access revoked message'


def _asana_revoked_access(result):
    error_description = result.error_response.get('error_description', '')
    if 'The user has revoked authorization' in error_description:
        result.error_code = error_codes.ACCESS_REVOKED
        result.error_message = error_description

import json
import logging

import urllib3.response as urllib3_response
from botocore.exceptions import ClientError

from integration import requests
from integration.exceptions import ConnectionResult, ErrorResponse
from integration.response_handler.boto3_error_handler import boto3_response_handler
from integration.response_handler.http_errors_handler import http_errors_handler_result
from integration.response_handler.slack_error_handler import slack_response_handler
from integration.response_handler.utils import (
    build_test_mode_response,
    graph_api_errors,
    is_valid_json_response,
)
from laika.utils.exceptions import ServiceException

logger = logging.getLogger(__name__)

SUCCESS = '200'

# Http Server Error Codes
SERVER_ERROR = '500'


# this method handles the response for the specific libraries,
# for example the GCP SDK and the Python request library
def raise_client_exceptions(
    response,
    is_graph_api: bool = False,
    check_expiration: bool = False,
    log_unknown_error: bool = True,
    raise_exception: bool = True,
    **kwargs
) -> ConnectionResult:
    connection_result = handle_response_status_code(
        response=response,
        is_graphql_api=is_graph_api,
        check_expiration=check_expiration,
        log_unknown_error=log_unknown_error,
        raise_exception=raise_exception,
        **kwargs
    )
    if connection_result.with_error() and raise_exception:
        raise connection_result.get_connection_result()

    return connection_result


def handle_response_status_code(
    response,
    is_graphql_api: bool = False,
    check_expiration: bool = False,
    log_unknown_error: bool = True,
    raise_exception: bool = True,
    **kwargs
) -> ConnectionResult:
    if response is None:
        raise ServiceException('The response is a null value.')
    error_response = ErrorResponse()
    error_response.expiration = check_expiration
    if (
        isinstance(response, (requests.Response, urllib3_response.HTTPResponse))
        and response.headers
    ):
        error_response.headers = response.headers

    response_object = _http_response_type(response, error_response, **kwargs)

    result = ConnectionResult(status_code=str(response_object.status))
    if result.is_success() and is_graphql_api and raise_exception:
        return graph_api_errors(response, result)

    if kwargs.get('is_slack_api', False):
        return slack_response_handler(response, result)

    if kwargs.get('is_boto3_response', False):
        return boto3_response_handler(response, result)

    if result.is_success():
        return result

    if str(response_object.status).startswith(('4', '5')):
        return http_errors_handler_result(result, error_response, log_unknown_error)

    return result


def _http_response_type(
    response, error_response: ErrorResponse, **kwargs
) -> ErrorResponse:
    if isinstance(response, requests.Response):
        error_response.status = response.status_code
        error_response.reason = response.reason
        error_response.response = is_valid_json_response(response)
        build_test_mode_response(response.url, error_response.response, **kwargs)
        return error_response
    if isinstance(response, urllib3_response.HTTPResponse):
        error_response.status = response.status
        error_response.reason = response.reason
        error_response.response = json.loads(response.data.decode('utf-8'))
        build_test_mode_response(response.geturl(), error_response.response, **kwargs)
        return error_response
    if isinstance(response, ClientError):
        status_code = response.response.get('ResponseMetadata', {}).get(
            'HTTPStatusCode'
        )
        error_reason = response.response.get('Error', {}).get('Code')
        error_response.status = status_code
        error_response.reason = error_reason
        return error_response

    raise ServiceException('Response object is not a valid type.')

import pytest
from httmock import response
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from integration.exceptions import (
    BadGatewayException,
    ConfigurationError,
    GatewayTimeoutException,
    ServiceUnavailableException,
    TimeoutException,
    TooManyRequests,
)
from integration.response_handler.handler import raise_client_exceptions

NOT_FOUND_ERROR_MESSAGE = 'Resource you have specified cannot be found.'
INCORRECT_CREDENTIALS_MESSAGE = 'Invalid authentication credentials'
INSUFFICIENT_PERMISSIONS_MESSAGE = 'The connection does not have admin privileges.'
TOO_MANY_REQUEST_ERROR_MESSAGE = 'Too Many Requests'
GATEWAY_TIMEOUT = 'Gateway Timeout'
SERVER_ERROR_MESSAGE = "There was a problem on vendor's end."
GRAPHQL_ERROR_MESSAGE = 'Provider GraphQL API error'
NONE_RESPONSE_ERROR_MESSAGE = 'The response is a null value.'
INVALID_RESPONSE_TYPE_ERROR_MESSAGE = 'Response object is not a valid type.'
EXPIRED_ACCOUNT_ERROR_MESSAGE = (
    'The token or account provided has expired or expired credentials'
)
BAD_REQUEST = 'Bad request syntax or unsupported method'

UNKNOWN_ERROR_405_MESSAGE = (
    'The http status code 405 is not mapped in our error handler'
)
TIME_OUT_ERROR_MESSAGE = (
    'The request was well-formed but the server did '
    'not receive a complete request message '
    'within the time that it was prepared to wait.'
)


def mock_response(code, content):
    return response(status_code=code, content=content)


def json_response(message):
    return dict(message)


def test_not_found_error_404():
    json_res = json_response(dict(message='not found'))
    res = mock_response(404, json_res)
    with pytest.raises(ConfigurationError) as e:
        raise_client_exceptions(
            response=res,
        )

    assert str(e.value) == NOT_FOUND_ERROR_MESSAGE


def test_incorrect_credentials_error_401():
    json_res = json_response(dict(message='unauthorized'))
    res = mock_response(401, json_res)
    with pytest.raises(ConfigurationError) as e:
        raise_client_exceptions(
            response=res,
        )

    assert str(e.value) == INCORRECT_CREDENTIALS_MESSAGE


def test_insufficient_permissions_403():
    json_res = json_response(dict(message='forbidden'))
    res = mock_response(403, json_res)
    with pytest.raises(ConfigurationError) as e:
        raise_client_exceptions(
            response=res,
        )

    assert str(e.value) == INSUFFICIENT_PERMISSIONS_MESSAGE


def test_api_limit_429():
    json_res = json_response(dict(message='API limit exceeded'))
    res = mock_response(429, json_res)
    with pytest.raises(TooManyRequests) as e:
        raise_client_exceptions(
            response=res,
        )

    assert str(e.value) == TOO_MANY_REQUEST_ERROR_MESSAGE


def test_unknown_error_with_405():
    json_res = json_response(dict(message='Method not allowed'))
    res = mock_response(405, json_res)
    with pytest.raises(ConfigurationError) as e:
        raise_client_exceptions(
            response=res,
        )

    assert str(e.value) == UNKNOWN_ERROR_405_MESSAGE


def test_server_error_500():
    json_res = json_response(dict(message='something wrong in the provider server'))
    res = mock_response(500, json_res)
    with pytest.raises(ConfigurationError) as e:
        raise_client_exceptions(
            response=res,
        )

    assert str(e.value) == SERVER_ERROR_MESSAGE


def test_server_error_400():
    json_res = json_response(dict(message='bad request'))
    res = mock_response(400, json_res)
    with pytest.raises(ConfigurationError) as e:
        raise_client_exceptions(
            response=res,
        )

    assert str(e.value) == BAD_REQUEST


def test_check_expiration_flag_401():
    json_res = json_response(dict(message='expired credentials'))
    res = mock_response(401, json_res)
    with pytest.raises(ConfigurationError) as e:
        raise_client_exceptions(response=res, check_expiration=True)

    assert str(e.value) == EXPIRED_ACCOUNT_ERROR_MESSAGE


def test_graphql_api_error():
    json_res = json_response(dict(errors=dict(path='invalid key')))
    res = mock_response(200, json_res)
    with pytest.raises(ConfigurationError) as e:
        raise_client_exceptions(response=res, is_graph_api=True)

    assert str(e.value) == GRAPHQL_ERROR_MESSAGE


def test_exception_with_none_response():
    with pytest.raises(Exception) as e:
        raise_client_exceptions(
            response=None,
        )
    assert str(e.value) == NONE_RESPONSE_ERROR_MESSAGE


def test_invalid_http_response_type():
    with pytest.raises(Exception) as e:
        raise_client_exceptions(
            response=int,
        )
    assert str(e.value) == INVALID_RESPONSE_TYPE_ERROR_MESSAGE


def test_connected_timed_out_error():
    json_res = json_response(dict(message='request time out'))
    res = mock_response(408, json_res)
    with pytest.raises(TimeoutException) as e:
        raise_client_exceptions(
            response=res,
        )
    assert str(e.value) == 'Timeout Error.'


def test_gateway_timeout_504():
    json_res = json_response(dict(message='Gateway Timeout'))
    res = mock_response(504, json_res)

    with pytest.raises(GatewayTimeoutException) as e:
        raise_client_exceptions(response=res)

    assert str(e.value) == GATEWAY_TIMEOUT


retry_condition = (
    retry_if_exception_type(GatewayTimeoutException)
    | retry_if_exception_type(BadGatewayException)
    | retry_if_exception_type(ServiceUnavailableException)
)


def test_retry_on_gateway_timeout():
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(),
        reraise=True,
        retry=retry_condition,
    )
    def test_tenacity_retry_on_504():
        json_res = json_response(dict(message='Gateway Timeout'))
        res = mock_response(504, json_res)
        raise_client_exceptions(response=res)

    with pytest.raises(GatewayTimeoutException):
        test_tenacity_retry_on_504()

    assert test_tenacity_retry_on_504.retry.statistics['attempt_number'] == 3


def test_retry_on_bad_gateway():
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(),
        reraise=True,
        retry=retry_condition,
    )
    def test_tenacity_retry_on_502():
        json_res = json_response(dict(message='Bad Gateway'))
        res = mock_response(502, json_res)

        raise_client_exceptions(response=res)

    with pytest.raises(BadGatewayException):
        test_tenacity_retry_on_502()

    assert test_tenacity_retry_on_502.retry.statistics['attempt_number'] == 3


def test_retry_on_service_unavailable():
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(),
        reraise=True,
        retry=retry_condition,
    )
    def test_tenacity_retry_on_503():
        json_res = json_response(dict(message='Service Unavailable'))
        res = mock_response(503, json_res)

        raise_client_exceptions(response=res)

    with pytest.raises(ServiceUnavailableException):
        test_tenacity_retry_on_503()

    assert test_tenacity_retry_on_503.retry.statistics['attempt_number'] == 3

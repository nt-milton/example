import requests.exceptions
from tenacity import retry_if_exception_type

from integration.exceptions import (
    BadGatewayException,
    GatewayTimeoutException,
    ServiceUnavailableException,
    TimeoutException,
    TooManyRequests,
)

PAGE_SIZE = 50
NOT_APPLICABLE = 'N/A'
retry_condition = (
    retry_if_exception_type(ConnectionError)
    | retry_if_exception_type(TooManyRequests)
    | retry_if_exception_type(TimeoutException)
    | retry_if_exception_type(GatewayTimeoutException)
    | retry_if_exception_type(requests.exceptions.ReadTimeout)
    | retry_if_exception_type(requests.exceptions.Timeout)
    | retry_if_exception_type(ServiceUnavailableException)
    | retry_if_exception_type(BadGatewayException)
)

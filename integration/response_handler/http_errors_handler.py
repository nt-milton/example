import logging

from integration.exceptions import ConnectionResult, ErrorResponse
from integration.response_handler.http_status_factory import http_errors_factory
from integration.response_handler.utils import default_unknown_error

logger = logging.getLogger(__name__)


def http_errors_handler_result(
    result: ConnectionResult,
    error_response: ErrorResponse,
    log_unknown_error: bool = True,
) -> ConnectionResult:
    http_errors_dict = http_errors_factory()
    http_errors_dict.get(int(result.status_code), lambda *args: False)(
        error_response, result
    ) if http_errors_dict.get(int(result.status_code)) else default_unknown_error(
        error_response, result, log_unknown_error
    )
    return result

import logging
from datetime import datetime

from laika.constants import REQUEST_OPERATION_KEY
from laika.settings import ORIGIN_DEV, ORIGIN_LOCALHOST, ORIGIN_PROD, ORIGIN_STAGING

logger = logging.getLogger(__name__)

THRESHOLD_MS = 1000

API_QUERIES = [
    'operation: Query.resolve_objects',
    'operation: Query.resolve_all_object_elements',
    'operation: Query.resolve_object',
    'operation: Query.resolve_objects_paginated',
]

API_MUTATIONS = [
    'operation: CreateLaikaObject.mutate',
    'operation: UpdateLaikaObject.mutate',
    'operation: BulkDeleteLaikaObjects.mutate',
    'operation: BulkUploadObject.mutate',
]


def _get_all_laika_origins() -> list:
    return ORIGIN_LOCALHOST + ORIGIN_DEV + ORIGIN_STAGING + ORIGIN_PROD


def _is_operation_an_external_api(operation: str = None) -> bool:
    api_services = API_QUERIES + API_MUTATIONS
    return operation in api_services


def difference_in_milliseconds(start: datetime, end: datetime = datetime.now()) -> int:
    diff = end - start
    return int(diff.total_seconds() * 1000)


class APIRequestMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = datetime.now()
        response = self.get_response(request)
        operation = getattr(request, REQUEST_OPERATION_KEY, 'unknown operation')
        milliseconds = difference_in_milliseconds(start, datetime.now())

        if _is_operation_an_external_api(operation):
            _log_external_api_request_values(operation, request, response)

        slow_message = 'Slow: 🚫' if milliseconds > THRESHOLD_MS else 'Normal ✅'

        logger.info(
            f'END Request duration: {milliseconds}ms - {operation} - {slow_message}'
        )

        return response


def _get_log_values_from_request(request) -> dict:
    if request and request.headers:
        return {
            'origin': request.headers.get('Origin'),
            'host': request.headers.get('Host'),
            'user_agent': request.headers.get('User-Agent'),
            'body': request.body,
            'request_id': request.id,
        }
    return {}


def _log_external_api_request_values(operation: str, request, response) -> None:
    def _get_log_message(status: str = 'started') -> str:
        return (
            f'Request ID {request.id} - {status} - '
            f'Operation {operation} - '
            f'Host {log_values.get("host")} - '
            f'User-Agent {log_values.get("user_agent")} - '
            'External origin.'
        )

    log_values = _get_log_values_from_request(request)
    origin = log_values.get('origin')

    if origin in _get_all_laika_origins():
        # Just for Laika external API
        return

    logger.info(_get_log_message('Started'))
    request_body = str(log_values.get('body'))
    response_content = str(response.content)
    # Format [body and content] using value.decode('unicode_escape')
    logger.info(f'Request ID {request.id} - Body: {request_body}')
    logger.info(f'Request ID {request.id} - Content: {response_content}')
    logger.info(_get_log_message('Ended'))

import json
import logging
from json import JSONDecodeError
from typing import Any, Callable, List

from integration import error_codes as error_codes
from integration.exceptions import ConnectionResult, ErrorResponse
from integration.log_utils import connection_context
from integration.models import ConnectionAccount
from integration.test_mode import is_connection_on_test_mode, test_state

logger = logging.getLogger(__name__)


def default_unknown_error(
    error_response: ErrorResponse,
    result: ConnectionResult,
    log_unknown_error: bool = True,
) -> None:
    result.error_code = error_codes.OTHER
    result.error_message = (
        f'The http status code {error_response.status} is not mapped in our error'
        ' handler'
    )
    result.error_response = error_response.response
    if log_unknown_error:
        logger.warning(
            f'The http request status code is {error_response.status} and the '
            f'request response is: {error_response.response}, '
            'Please take a look if this is a new error code that could be mapped '
        )


def is_valid_json_response(response):
    try:
        return response.json()
    except JSONDecodeError:
        return {'message': 'The provider response is not valid JSON'}


def graph_api_errors(response, result: ConnectionResult) -> ConnectionResult:
    if 'errors' in response.json():
        result.status_code = error_codes.DEFAULT_GRAPHQL_ERROR
        result.error_code = error_codes.PROVIDER_GRAPHQL_ERROR
        result.error_message = 'Provider GraphQL API error'
        result.error_response = response.json()

    return result


def build_test_mode_response(url, response, **kwargs):
    context = connection_context.get()
    connection_account: ConnectionAccount = (
        context.connection if context else kwargs.get('connection_account')
    )
    if connection_account and is_connection_on_test_mode(connection_account.id):
        raw = {'REQUEST URL:': url, 'RESPONSE:': response}
        test_state.save_raw_data_in_test_mode(
            connection_account.id, json.dumps(raw, indent=4)
        )


def get_paginated_api_response(
    api_request: Callable[[int, int], Any],
    next_iteration_condition: Callable,
    initial_page: int = 0,
    page_size: int = 50,
    iter_limit: int = 1000,
    objects_to_append: Callable = None,
) -> List[Any]:
    responses: List[Any] = []
    current_page: int = initial_page

    while current_page < iter_limit:
        response = api_request(current_page, page_size)
        responses.extend(
            objects_to_append(response)
        ) if objects_to_append else responses.extend(response)
        if not next_iteration_condition(
            current_page=current_page, page_size=page_size, response=response
        ):
            break
        current_page = current_page + 1

    return responses


def log_metrics():
    context = connection_context.get()
    if context:
        metrics = context.custom_metric
        logger.info(f'Connection account {context.connection.id} - {metrics}')

from integration import error_codes
from integration.exceptions import ConnectionResult, TimeoutException


def slack_response_handler(response, result: ConnectionResult) -> ConnectionResult:
    slack_ok = response.json().get('ok')
    error_code = response.json().get('error')
    if slack_ok and not error_code:
        return result

    result.error_message = f'Slack error happened with the message: {error_code}'
    result.error_response = response.json()

    slack_error_codes = {
        'token_expired': error_codes.EXPIRED_TOKEN,
        'token_revoked': error_codes.ACCESS_REVOKED,
        'account_inactive': error_codes.ACCESS_REVOKED,
        'access_denied': error_codes.INSUFFICIENT_PERMISSIONS,
        'no_permission': error_codes.INSUFFICIENT_PERMISSIONS,
        'request_timeout': error_codes.CONNECTION_TIMEOUT,
        'service_unavailable': error_codes.PROVIDER_SERVER_ERROR,
    }
    result.error_code = slack_error_codes.get(error_code, error_codes.OTHER)

    if result.error_code == error_codes.CONNECTION_TIMEOUT:
        raise TimeoutException('Timeout Error.')

    return result

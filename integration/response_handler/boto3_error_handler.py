from botocore.exceptions import ClientError

from integration import error_codes
from integration.exceptions import ConnectionResult


def boto3_response_handler(response, result: ConnectionResult) -> ConnectionResult:
    if isinstance(response, ClientError):
        error_message = response.response.get('Error', {}).get('Message', '')
        error_code = response.response.get('Error', {}).get('Code', '')

        result.error_message = f'AWS error happened with the message: {error_message}'
        result.error_response = response.response

        # Reference to AWS common errors:
        # https://docs.aws.amazon.com/IAM/latest/APIReference/CommonErrors.html
        aws_error_codes = {
            'InvalidRegionError': error_codes.PROVIDER_SERVER_ERROR,
            'InternalError': error_codes.PROVIDER_SERVER_ERROR,
            'AccessDeniedException': error_codes.ACCESS_REVOKED,
            'IncompleteSignature': error_codes.BAD_CLIENT_CREDENTIALS,
            'InternalFailure': error_codes.PROVIDER_SERVER_ERROR,
            'InvalidClientTokenId': error_codes.BAD_CLIENT_CREDENTIALS,
            'NotAuthorized': error_codes.INSUFFICIENT_PERMISSIONS,
            'ServiceUnavailable': error_codes.PROVIDER_SERVER_ERROR,
        }
        result.error_code = aws_error_codes.get(error_code, error_codes.OTHER)

    return result

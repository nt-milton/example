import logging
from datetime import datetime, timezone
from typing import Dict, List, Union

import boto3
from botocore.exceptions import ClientError
from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential

from integration.settings import AWS_CONFIG, AWS_EXTERNAL_ID
from laika.utils.exceptions import ServiceException

from ..exceptions import ConfigurationError
from ..integration_utils.constants import retry_condition
from ..log_utils import log_action, log_request
from ..models import ConnectionAccount
from ..response_handler.handler import raise_client_exceptions
from ..retry import retry

AWS_DEFAULT_REGIONS = [
    'us-east-1',
    'us-east-2',
    'us-west-1',
    'us-west-2',
    'eu-central-1',
    'eu-west-1',
    'eu-west-2',
    'eu-south-1',
    'eu-west-3',
    'eu-north-1',
    'us-gov-east-1',
    'us-gov-west-1',
    'ap-south-1',
]

logger_name = __name__
logger = logging.getLogger(logger_name)

AWS_ATTEMPTS = 3


def _log_values(is_generator: bool = False):
    return dict(vendor_name='AWS', logger_name=logger_name, is_generator=is_generator)


def get_sts_client() -> boto3.client:
    return boto3.client('sts', config=AWS_CONFIG)


@log_action(**_log_values())
def get_external_role_arn(connection_account: ConnectionAccount) -> str:
    arn = connection_account.configuration_state.get('credentials').get(
        'external_role_arn'
    )
    if not arn:
        message = f'Not ARN in connection account: {connection_account.id}'
        logger.warning(message)
        raise ServiceException(message)
    return arn.strip()


@retry(
    stop=stop_after_attempt(AWS_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_if_exception_type(ConfigurationError),
)
@log_action(**_log_values())
def assume_role_credentials(connection_account: ConnectionAccount) -> tuple:
    try:
        sts_client = get_sts_client()
        log_request(
            'assume_role',
            'assume_role_credentials',
            logger_name,
            connection_account=connection_account,
        )
        response = sts_client.assume_role(
            RoleArn=get_external_role_arn(connection_account),
            RoleSessionName='assume_role_session',
            ExternalId=AWS_EXTERNAL_ID,
        )
    except Exception as e:
        error_message = (
            'Error assuming credentials role in '
            f'connection {connection_account.id}. Error {e}'
        )
        logger.warning(error_message)
        raise ConfigurationError.bad_client_credentials(error_message)

    if 'Credentials' not in response:
        error_message = (
            f'Credentials not in the response for connection {connection_account.id}.'
        )
        logger.warning(error_message)
        raise ConfigurationError.bad_client_credentials(error_message)

    connection_account.authentication['access_key_id'] = response['Credentials'][
        'AccessKeyId'
    ]
    connection_account.authentication['secret_access_key'] = response['Credentials'][
        'SecretAccessKey'
    ]
    connection_account.authentication['session_token'] = response['Credentials'][
        'SessionToken'
    ]
    expiration_timestamp = (
        response['Credentials']['Expiration'].replace(tzinfo=timezone.utc).timestamp()
    )
    connection_account.authentication['token_expiration_time'] = expiration_timestamp
    connection_account.authentication['aws_regions'] = validate_regions(
        connection_account
    )
    connection_account.save()

    return (
        response['Credentials']['AccessKeyId'],
        response['Credentials']['SecretAccessKey'],
        response['Credentials']['SessionToken'],
        expiration_timestamp,
    )


@log_action(**_log_values())
def create_external_organization_client(
    connection_account: ConnectionAccount,
) -> boto3.client:
    try:
        authentication_data = connection_account.authentication
        log_request(
            'organizations',
            'create_external_organization_client',
            logger_name,
            connection_account=connection_account,
        )
        return boto3.client(
            'organizations',
            config=AWS_CONFIG,
            aws_access_key_id=authentication_data.get('access_key_id'),
            aws_secret_access_key=authentication_data.get('secret_access_key'),
            aws_session_token=authentication_data.get('session_token'),
        )
    except (ClientError, Exception) as error:
        raise_client_exceptions(response=error, is_boto3_response=True)


@log_action(**_log_values())
def create_external_iam_client(connection_account: ConnectionAccount) -> boto3.client:
    try:
        authentication_data = connection_account.authentication
        log_request(
            'iam',
            'create_external_iam_client',
            logger_name,
            connection_account=connection_account,
        )
        return boto3.client(
            'iam',
            config=AWS_CONFIG,
            aws_access_key_id=authentication_data.get('access_key_id'),
            aws_secret_access_key=authentication_data.get('secret_access_key'),
            aws_session_token=authentication_data.get('session_token'),
        )
    except (ClientError, Exception) as error:
        raise_client_exceptions(response=error, is_boto3_response=True)


@log_action(**_log_values())
def get_users(iam_client: boto3.client) -> list:
    log_request('list_users', 'get_users', logger_name)
    users = iam_client.list_users().get('Users', [])
    if not users:
        logger.info('Users is empty')
    return users


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_roles_policies(iam_client: boto3.client) -> tuple:
    roles = []
    policies = []
    marker = None
    is_truncated = True
    while is_truncated:
        if marker:
            log_request(
                'get_account_authorization_details',
                'get_roles_policies. marker',
                logger_name,
            )
            account_details = iam_client.get_account_authorization_details(
                Filter=['LocalManagedPolicy', 'AWSManagedPolicy', 'Role'], Marker=marker
            )
        else:
            log_request(
                'get_account_authorization_details', 'get_roles_policies', logger_name
            )
            account_details = iam_client.get_account_authorization_details(
                Filter=['LocalManagedPolicy', 'AWSManagedPolicy', 'Role']
            )
        is_truncated = account_details.get('IsTruncated', False)
        marker = account_details.get('Marker', None)
        roles += account_details.get('RoleDetailList', [])
        policies += account_details.get('Policies', [])
    return roles, policies


@log_action(**_log_values())
def user_has_mfa(iam_client: boto3.client, user_name: str) -> bool:
    log_request('list_mfa_devices', 'user_has_mfa', logger_name)
    mfa_devices = iam_client.list_mfa_devices(UserName=user_name)['MFADevices']
    return True if mfa_devices else False


@log_action(**_log_values())
def user_is_admin(iam_client: boto3.client, user_name: str) -> bool:
    is_admin = False
    groups = get_users_groups(iam_client, user_name)['Groups']
    for group in groups:
        log_request('list_attached_group_policies', 'user_is_admin', logger_name)
        group_policies = [
            p['PolicyName']
            for p in iam_client.list_attached_group_policies(
                GroupName=group['GroupName']
            )['AttachedPolicies']
        ]
        if 'AdministratorAccess' in group_policies:
            is_admin = True
            break

    log_request('list_attached_user_policies', 'user_is_admin', logger_name)
    user_policies = [
        p['PolicyName']
        for p in iam_client.list_attached_user_policies(UserName=user_name)[
            'AttachedPolicies'
        ]
    ]
    if 'AdministratorAccess' in user_policies:
        is_admin = True
    return is_admin


@log_action(**_log_values())
def get_users_groups(iam_client: boto3.client, user_name: str) -> dict:
    log_request('list_groups_for_user', 'get_users_groups', logger_name)
    return iam_client.list_groups_for_user(UserName=user_name)


@log_action(**_log_values())
def get_organization(
    organization_client: boto3.client, connection_account: ConnectionAccount
) -> Dict:
    try:
        log_request(
            'describe_organization',
            'get_organization',
            logger_name,
            connection_account=connection_account,
        )
        organization = organization_client.describe_organization()['Organization']
    except (ClientError, Exception) as error:
        logger.info(
            f'The account is not a member of an organization: {error}. '
            f'Connection account: {connection_account.id}'
        )
        return {}
    return organization


@log_action(**_log_values())
def get_root_account(
    organization_client: boto3.client,
    account_id: str,
    connection_account: ConnectionAccount,
) -> Union[Dict, None]:
    try:
        log_request(
            'describe_account',
            'get_root_account',
            logger_name,
            connection_account=connection_account,
        )
        return organization_client.describe_account(AccountId=account_id)['Account']
    except (ClientError, Exception) as error:
        logger.info(
            f'Missing permissions to retrieve account information: {error}. '
            f'Connection account: {connection_account.id}'
        )
        return None


@log_action(**_log_values())
def validate_regions(connection_account: ConnectionAccount) -> List:
    valid_regions = []
    authentication_data = connection_account.authentication
    for region in AWS_DEFAULT_REGIONS:
        log_request(
            'dynamodb',
            f'validate_regions: {region}',
            logger_name,
            connection_account=connection_account,
        )
        dynamo_db_client = boto3.client(
            'dynamodb',
            region_name=region,
            config=AWS_CONFIG,
            aws_access_key_id=authentication_data.get('access_key_id'),
            aws_secret_access_key=authentication_data.get('secret_access_key'),
            aws_session_token=authentication_data.get('session_token'),
        )
        try:
            dynamo_db_client.list_tables()
            valid_regions.append(region)
        except ClientError:
            log_request(
                'list_tables',
                f'Not valid region: {region}',
                logger_name,
                connection_account=connection_account,
            )
            continue
    return valid_regions


def is_token_expired(connection_account: ConnectionAccount) -> bool:
    if 'token_expiration_time' in connection_account.authentication:
        current_token_expiration = connection_account.authentication.get(
            'token_expiration_time'
        )
        now = datetime.now(timezone.utc)
        timestamp_now = now.replace(tzinfo=timezone.utc).timestamp()
        if current_token_expiration > timestamp_now:
            return False
    return True

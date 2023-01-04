import json
import uuid
from pathlib import Path
from typing import Dict, Set, Tuple

from botocore.exceptions import ClientError
from cryptography.fernet import Fernet, InvalidToken

from integration.encryption_utils import decrypt_value
from integration.error_codes import USER_INPUT_ERROR
from integration.exceptions import ConfigurationError
from integration.models import ConnectionAccount
from integration.settings import (
    INTEGRATIONS_ENCRYPTION_KEY,
    LAIKA_PUBLIC_TEMPLATES_BUCKET,
)
from laika.aws.s3 import s3_client

TEST_DIR = Path(__file__).parent

GRAPH = 'GRAPH'
# TEMPLATE STATES
DEPLOY = 'DEPLOY'
DEPLOYED = 'DEPLOYED'
# TEMPLATE STATE KEYS
TEMPLATE_STATE = 'templateState'
TEMPLATE_KEY = 'templateKey'
OBJECT_ID = 'objectId'
SETTINGS = 'settings'
EXPIRATION = 'secretExpiration'
# ERRORS FOR EMPTY RESPONSES WITH MICROSOFT GRAPH
ERROR_OBJECT_ID = (
    'The service principal (Application) was not found with the object id that was'
    ' provided'
)
ERROR_APP_ID = 'Application not found with provided ID'
AZURE_ERROR_REQUEST_DENIED = 'Authorization_RequestDenied'
AZURE_ERROR_UNKNOWN = 'UnknownError'
AZURE_SERVICE_NOT_AVAILABLE = 'serviceNotAvailable'

ADMIN_ROLES = [
    'Owner',
    'Azure Kubernetes Service Cluster Admin Role',
    'Security Admin',
    'Virtual Machine Administrator Login',
    'User Access Administrator',
    'Hybrid Server Resource Administrator',
    'Azure Connected Machine Resource Administrator',
    'Experimentation Administrator',
    'Remote Rendering Administrator',
    'Hierarchy Settings Administrator',
    'Key Vault Administrator',
    'Azure Arc Kubernetes Cluster Admin',
    'Azure Arc Kubernetes Admin',
    'Azure Kubernetes Service RBAC Cluster Admin',
    'Azure Kubernetes Service RBAC Admin',
    'Device Update Administrator',
    'Device Update Content Administrator',
    'Device Update Deployments Administrator',
    'Cognitive Services Metrics Advisor Administrator',
    'AgFood Platform Service Admin',
    'Project Babylon Data Source Administrator',
    'Media Services Account Administrator',
    'Media Services Live Events Administrator',
    'Media Services Policy Administrator',
    'Media Services Streaming Endpoints Administrator',
    'Grafana Admin',
    'Azure Arc VMware Administrator role',
    'Chamber Admin',
    'Windows Admin Center Administrator Login',
    'Compute Gallery Sharing Admin',
    'DevCenter Project Admin',
    'Azure Arc ScVmm Administrator role',
]


def _get_template() -> Dict:
    path = TEST_DIR / 'template/azure_role_template.json'
    template = open(path, 'r').read()
    return json.loads(template)


def add_object_id(object_id: str) -> Dict:
    template = _get_template()
    template['parameters']['principalId']['defaultValue'] = object_id
    return template


def upload_custom_role_template(connection_account: ConnectionAccount):
    object_id = connection_account.configuration_state['credentials']['objectId']
    template_string = add_object_id(object_id)
    try:
        template_state = connection_account.configuration_state[SETTINGS][
            TEMPLATE_STATE
        ]
        if TEMPLATE_KEY in template_state:
            key = template_state[TEMPLATE_KEY]
            upload_json_to_s3(key, template_string, connection_account)
        else:
            key = f'azure-{uuid.uuid4()}.json'
            upload_json_to_s3(key, template_string, connection_account)

    except ClientError as error:
        raise ConfigurationError.other_error(error.response)


def upload_json_to_s3(
    template_key: str, template_body: Dict, connection_account: ConnectionAccount
):
    s3_client.put_object(
        ACL='public-read',
        Body=json.dumps(template_body, indent=2),
        Key=template_key,
        Bucket=LAIKA_PUBLIC_TEMPLATES_BUCKET,
        ContentType='application/json',
    )
    template_state = {
        'state': DEPLOYED,
        'templateKey': template_key,
        'templateUrl': build_template_url(template_key),
    }
    connection_account.configuration_state[SETTINGS][TEMPLATE_STATE] = template_state


def build_template_url(template_key: str) -> str:
    return f'https://{LAIKA_PUBLIC_TEMPLATES_BUCKET}.s3.amazonaws.com/{template_key}'


def delete_object_template(key: str) -> None:
    try:
        s3_client.delete_object(Key=key, Bucket=LAIKA_PUBLIC_TEMPLATES_BUCKET)
    except ClientError as error:
        raise ConfigurationError.other_error(error.response)


def handle_azure_error(response: Dict, message: str) -> None:
    error_code = response.get('error', {}).get('code')
    if error_code:
        if error_code == AZURE_ERROR_REQUEST_DENIED:
            raise ConfigurationError.insufficient_permission(response)

        elif (
            error_code == AZURE_ERROR_UNKNOWN
            or error_code == AZURE_SERVICE_NOT_AVAILABLE
        ):
            raise ConfigurationError.provider_server_error(response)

        else:
            raise ConfigurationError.other_error(response)

    if not response.get('value'):
        error = _custom_empty_response_error(message)
        raise ConfigurationError(
            error_code=USER_INPUT_ERROR, error_response=error, error_message=message
        )


def _custom_empty_response_error(message: str) -> dict:
    return {'error': {'code': 'Not found or invalid params', 'message': message}}


def get_role_from_definition(subscription_id: str) -> str:
    return (
        f'/subscriptions/{subscription_id}/'
        'providers/Microsoft.Authorization/roleDefinitions/'
    )


def _has_admin_permissions(permission: str, role_names: Set[str]) -> bool:
    return (
        ('write' in permission or '/*' in permission or '/*/write' in permission)
        and '/*/read' not in permission
    ) or (bool(set(role_names) & set(ADMIN_ROLES)))


def get_is_admin_and_role_names(roles: list[dict]) -> Tuple[list, bool]:
    role_names = {role_name['roleName'] for role_name in roles}
    for role in roles:
        if role.get('roleType') == 'CustomRole':
            for permission in role.get('permissions', []):
                return list(role_names), _has_admin_permissions(permission, role_names)

    return list(role_names), bool(role_names & set(ADMIN_ROLES))


def validate_or_encrypt_value(connection_account: ConnectionAccount) -> None:
    credentials: dict = connection_account.credentials
    client_secret: str = credentials.get('clientSecret', '')
    f_key = Fernet(str.encode(INTEGRATIONS_ENCRYPTION_KEY))
    try:
        decrypt_value(client_secret)
    except InvalidToken:
        secret_encrypted = f_key.encrypt(str.encode(client_secret)).decode()
        credentials['clientSecret'] = secret_encrypted
        connection_account.configuration_state['credentials'] = credentials
        connection_account.save()

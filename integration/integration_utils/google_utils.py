import base64
import json

from cryptography.fernet import InvalidToken

from integration.encryption_utils import decrypt_value, encrypt_value
from integration.models import ConnectionAccount
from objects.system_types import User


def get_decrypted_or_encrypt_gcp_file(connection_account: ConnectionAccount) -> str:
    credentials_file = connection_account.credentials.get('credentialsFile', [])
    if len(credentials_file) < 1:
        return ''
    file = credentials_file[0]
    try:
        return decrypt_value(file.get('file'))
    except InvalidToken:
        encrypted_value = encrypt_value(file.get('file'))
        connection_account.credentials['credentialsFile'][0]['file'] = encrypted_value
        connection_account.save()
        return decrypt_value(encrypted_value)


def convert_base64_to_json(credentials_file):
    try:
        json_credentials = base64.b64decode(credentials_file)
        return json.loads(json_credentials)
    except Exception as error:
        raise ValueError('Cannot decode base64 file', error)


def get_json_credentials(connection_account):
    credentials_file_body = get_decrypted_or_encrypt_gcp_file(connection_account)
    credentials_json = convert_base64_to_json(credentials_file_body)
    return credentials_json


def map_users_response(user, connection_name, source_system):
    organizations = user.get('organizations')
    organization = organizations[0] if organizations else {}
    lo_user = User()
    lo_user.id = user['id']
    lo_user.first_name = user['name']['givenName']
    lo_user.last_name = user['name']['familyName']
    lo_user.title = organization.get('title', '')
    lo_user.email = user['primaryEmail']
    lo_user.organization_name = user['orgUnitPath'].rpartition('/')[2]
    lo_user.is_admin = user['isAdmin']
    lo_user.roles = user.get('roles', '')
    lo_user.groups = ''
    lo_user.mfa_enabled = user['isEnrolledIn2Sv']
    lo_user.mfa_enforced = user['isEnforcedIn2Sv']
    lo_user.source_system = source_system
    lo_user.connection_name = connection_name
    return lo_user.data()

from cryptography.fernet import Fernet, InvalidToken

from integration.models import ConnectionAccount
from integration.settings import INTEGRATIONS_ENCRYPTION_KEY

f_key = Fernet(str.encode(INTEGRATIONS_ENCRYPTION_KEY))


def decrypt_value(value: str) -> str:
    return f_key.decrypt(str.encode(value), ttl=None).decode()


def encrypt_value(value: str):
    return f_key.encrypt(str.encode(value)).decode()


def get_decrypted_or_encrypted_value(
    credentials_key: str, connection_account: ConnectionAccount
) -> str:
    authentication_value = connection_account.authentication.get(credentials_key)
    credentials_value = (
        authentication_value
        if authentication_value
        else connection_account.credentials.get(credentials_key)
    )
    if credentials_value:
        try:
            return decrypt_value(credentials_value)
        except InvalidToken:
            encrypted_value = encrypt_value(credentials_value)
            connection_account.credentials[credentials_key] = encrypted_value
            connection_account.save()
            return decrypt_value(encrypted_value)
    else:
        raise ValueError(
            f'The value: {credentials_key} to be encrypted does not exist in the'
            ' credentials field'
        )


def get_decrypted_or_encrypted_auth_value(connection_account: ConnectionAccount) -> str:
    access_token = connection_account.access_token
    add_encryption = connection_account.integration.metadata.get('add_encryption')
    if not access_token or not add_encryption:
        return access_token
    try:
        return decrypt_value(access_token)
    except InvalidToken:
        encrypted_value = encrypt_value(access_token)
        connection_account.authentication['access_token'] = encrypted_value
        connection_account.save()
        return decrypt_value(encrypted_value)

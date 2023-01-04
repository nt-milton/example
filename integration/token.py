from datetime import datetime
from typing import Callable

import jwt

from integration.encryption_utils import get_decrypted_or_encrypted_auth_value
from integration.models import ConnectionAccount

TokenProvider = Callable[[], str]
TokenCreator = Callable[[str], tuple[str, str]]

JWT_DECODE_OPTIONS = {
    'verify_signature': False,
    'verify_iat': False,
    'verify_nbf': False,
    'verify_exp': False,
    'verify_iss': False,
    'verify_aud': False,
}


def _token_requires_renew(access_token: str) -> bool:
    try:
        token_payload = jwt.decode(access_token, options=JWT_DECODE_OPTIONS)
        token_expiration_date = datetime.fromtimestamp(token_payload['exp'])
        now = datetime.now(tz=token_expiration_date.tzinfo)
        minutes_for_expiration = (token_expiration_date - now).total_seconds() // 60
    except jwt.InvalidTokenError:
        minutes_for_expiration = 0

    return minutes_for_expiration <= 5


def build_token_provider(
    connection_account: ConnectionAccount,
    create_access_token: TokenCreator,
) -> TokenProvider:
    get_access_token = build_get_access_token(create_access_token)

    def next_token() -> str:
        return get_access_token(connection_account)

    return next_token


def build_get_access_token(
    create_access_token: TokenCreator,
) -> Callable[[ConnectionAccount], str]:
    def get_access_token(connection_account: ConnectionAccount) -> str:
        access_token = get_decrypted_or_encrypted_auth_value(connection_account)
        if not access_token or _token_requires_renew(access_token):
            update_tokens(connection_account, create_access_token)
            return get_decrypted_or_encrypted_auth_value(connection_account)
        return access_token

    return get_access_token


def _update_connection_tokens(
    connection_account: ConnectionAccount, access_token: str, refresh_token: str
) -> None:
    connection_account.authentication['access_token'] = access_token
    get_decrypted_or_encrypted_auth_value(connection_account)
    if refresh_token:
        connection_account.authentication['refresh_token'] = refresh_token


def update_tokens(
    connection_account: ConnectionAccount, create_access_token: TokenCreator
) -> None:
    prev_token = connection_account.authentication['refresh_token']
    access_token, refresh_token = create_access_token(prev_token)
    _update_connection_tokens(connection_account, access_token, refresh_token)
    connection_account.save()

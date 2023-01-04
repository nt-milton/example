from collections import namedtuple

from integration import requests
from integration.encryption_utils import decrypt_value, get_decrypted_or_encrypted_value
from integration.models import ConnectionAccount
from integration.response_handler.handler import raise_client_exceptions
from integration.utils import wait_if_rate_time_api

Keys = namedtuple("Keys", ("client_id", "client_secret", "identifier", "domain"))


def keys(connection_account: ConnectionAccount) -> Keys:
    credential = connection_account.configuration_state.get('credentials')
    client_secret = get_decrypted_or_encrypted_value('clientSecret', connection_account)
    return Keys(
        client_id=credential.get('clientID'),
        client_secret=client_secret,
        identifier=credential.get('identifier'),
        domain=credential.get('domain'),
    )


def get_token(connection_account):
    client_id, client_secret, identifier, domain = keys(connection_account)
    url = f'https://{domain}/oauth/token'
    data = dict(
        grant_type='client_credentials',
        client_id=client_id,
        client_secret=client_secret,
        audience=identifier,
    )
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    response = requests.post(url=url, data=data, headers=headers)
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json()


def get_users(connection_account):
    return make_auth0_api_request(connection_account, 'users')


def get_user_organizations(user_id, connection_account):
    return make_auth0_api_request(connection_account, f'users/{user_id}/organizations')


def get_user_roles(user_id, connection_account):
    return make_auth0_api_request(connection_account, f'users/{user_id}/roles')


def make_auth0_api_request(connection_account, path=''):
    auth0_keys = keys(connection_account)
    url = f'https://{auth0_keys.domain}/api/v2/{path}'
    token = decrypt_value(connection_account.authentication.get("access_token"))
    headers = {'authorization': f'Bearer {token}', 'content-type': 'application/json'}
    response = requests.get(url=url, headers=headers)
    return response.json()

import json
import logging
from json.decoder import JSONDecodeError
from os.path import exists
from typing import List, Mapping, Optional, Tuple

import jwt
import requests
from okta_jwt_verifier.exceptions import JWTValidationException

from laika.cache import cache_func
from laika.constants import AUTH_GROUPS, OKTA
from laika.okta.api import OktaApi
from laika.settings import OKTA_CLIENT_ID, OKTA_CLIENT_SECRET
from user.models import User

logger = logging.getLogger(__name__)

OKTA_KEYS_JSON = 'okta_keys.json'
AUTH_HEYLAIKA = 'https://auth.heylaika.com'

IDP = 'idp'  # Identity Provider
KID = 'kid'  # Token Key
ROLE = 'role'  # User role
EXP = ('exp',)  # Token Expiration
IAT = ('iat',)  # Issued At
ISS = 'iss'

OKTA_KEYS_URL = (
    f'https://laika.okta.com/oauth2/v1/keys?client_id={OKTA_CLIENT_ID}'
    f'&client_secret={OKTA_CLIENT_SECRET}'
)

OktaApi = OktaApi()


public_keys = {}
try:
    logger.info('Trying to read keys from JSON file')
    with open(OKTA_KEYS_JSON, 'r') as openfile:
        for jwk in json.load(openfile)['keys']:
            public_keys[jwk[KID]] = jwt.algorithms.RSAAlgorithm.from_jwk(
                json.dumps(jwk)
            )
        logger.info('Keys were loaded from JSON file')
except Exception as global_e:
    logger.exception(f'Error reading okta keys from json file: {global_e}')


def exists_okta_keys_json() -> bool:
    return exists(OKTA_KEYS_JSON)


def is_kid_valid(kid: str) -> Optional[dict]:
    return public_keys.get(kid)


def get_okta_key_from_server():
    try:
        okta_keys_response = requests.get(OKTA_KEYS_URL).json()
        with open(OKTA_KEYS_JSON, 'w') as outfile:
            outfile.write(json.dumps(okta_keys_response, indent=4))
            logger.info('Saving okta keys in JSON file!')
        for jwk_pair in okta_keys_response['keys']:
            public_keys[jwk_pair[KID]] = jwt.algorithms.RSAAlgorithm.from_jwk(
                json.dumps(jwk_pair)
            )
            logger.info('Updating public_keys!')
    except (JSONDecodeError, requests.ConnectTimeout, requests.ReadTimeout) as e:
        logger.exception(f'Error loading okta keys {e}')


def __load_okta_keys(force_request=False):
    if force_request or not exists_okta_keys_json():
        logger.info('Requesting okta keys from server!')
        get_okta_key_from_server()


__load_okta_keys()


@cache_func
def get_token_apps(
    verified_token: Mapping, **kwargs
) -> Tuple[List[str], Optional[User]]:
    formatted_apps = []
    okta_user = OktaApi.get_user_by_email(verified_token.get('email'))

    if not okta_user:
        return [], None

    apps = OktaApi.get_user_apps(okta_user.id)

    for app in apps:
        print(app)
        formatted_apps.append(app.name)

    return formatted_apps, okta_user


def decode_okta(token: str, verify_exp=True, verify=True, key=None):
    try:
        decoded_token = decode(token, verify_exp, verify, key)
        if not decoded_token:
            return None

        if not decoded_token.get('sub'):
            logger.warning('Token does not have sub claim')
            return None

        token_email = decoded_token['email']
        user_apps, okta_user = get_token_apps(
            decoded_token,
            cache_name=f'apps_for_{token_email}',
            time_out=300,  # 5minutes
        )

        if not okta_user or not user_apps:
            return None

        decoded_token[AUTH_GROUPS] = user_apps
        decoded_token['username'] = decoded_token['sub']
        decoded_token[IDP] = OKTA
        if hasattr(okta_user.profile, 'laika_role') and okta_user.profile.laika_role:
            decoded_token[ROLE] = okta_user.profile.laika_role

        return decoded_token
    except JWTValidationException as e:
        logger.exception(f'error trying to decode okta token validation failed: {e}')
        raise jwt.ExpiredSignatureError('Signature has expired')
    except Exception as e:
        logger.exception(f'error trying to decode okta token: {e}')
        raise e


async def decode_okta_async(token: str, verify_exp=True, verify=True, key=None):
    try:
        decoded_token = decode(token, verify_exp, verify, key)
        if not decoded_token:
            return None

        return decoded_token
    except JWTValidationException as e:
        logger.exception(f'error trying to decode okta tokenvalidation failed: {e}')
        raise jwt.ExpiredSignatureError('Signature has expired')
    except Exception as e:
        logger.exception(f'error trying to decode okta token: {e}')
        raise e


def decode(token: str, verify_exp=True, verify=True, key=None) -> Optional[dict]:
    try:
        kid = jwt.get_unverified_header(token)['kid']
    except Exception as e:
        logger.exception(f'Error verifying okta token: {e}')
        return None

    if not key and verify:
        key = get_kid_if_not_exists_retry(kid)

    decoded_token = jwt.decode(
        token,
        verify=verify,
        options={'verify_aud': False, 'verify_exp': verify_exp},
        key=key,
        algorithms=['RS256'],
    )

    decoded_token[IDP] = OKTA
    return decoded_token


def is_issued_by_okta(token: str) -> bool:
    try:
        decoded = jwt.decode(
            token, options={'verify_aud': False, 'verify_signature': False}
        )
        return decoded[ISS] == AUTH_HEYLAIKA
    except Exception as e:
        logger.warning(f'Error decoding token: {e}')
        return False


def get_kid_if_not_exists_retry(kid: str, retry=0) -> Optional[dict]:
    if retry == 3:
        return None

    key = is_kid_valid(kid)
    if not key:
        logger.info(f'Force updating okta keys from server. Try: {retry}')
        __load_okta_keys(force_request=True)
        return get_kid_if_not_exists_retry(kid, retry + 1)
    return key

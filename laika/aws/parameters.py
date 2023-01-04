import base64
import hashlib
import hmac
import os

import boto3

from laika.settings import DJANGO_SETTINGS

ENVIRONMENT = os.getenv('ENVIRONMENT')
LEGACY_AWS_ACCESS_KEY = os.getenv('LEGACY_AWS_ACCESS_KEY')
LEGACY_AWS_SECRET_ACCESS_KEY = os.getenv('LEGACY_AWS_SECRET_ACCESS_KEY')

env = ENVIRONMENT
if ENVIRONMENT == 'prod':
    env = 'production'
elif ENVIRONMENT == 'local' or ENVIRONMENT == 'dev':
    env = 'development'


def get_parameter(name):
    ssm = boto3.client(
        'ssm',
        region_name='us-east-1',
        aws_access_key_id=LEGACY_AWS_ACCESS_KEY,
        aws_secret_access_key=LEGACY_AWS_SECRET_ACCESS_KEY,
    )
    response = ssm.get_parameter(Name=name, WithDecryption=True)
    return response['Parameter']['Value']


def get_secret_hash(secret, user_name, app_client_id):
    key = bytes(secret, 'utf-8')
    msg = bytes(user_name + app_client_id, 'utf-8')
    new_digest = hmac.new(key, msg, hashlib.sha256).digest()
    return base64.b64encode(new_digest).decode()


def get_admin_auth_token():
    user_pool_id = DJANGO_SETTINGS.get('LEGACY_POOL_ID')
    app_client_id = DJANGO_SETTINGS.get('LEGACY_APP_CLIENT_ID')
    app_client_secret = DJANGO_SETTINGS.get('LEGACY_APP_CLIENT_SECRET')
    user_name = DJANGO_SETTINGS.get('LEGACY_SUPERADMIN')
    password = DJANGO_SETTINGS.get('LEGACY_SUPERADMIN_PASSWORD')

    SECRET_HASH = get_secret_hash(app_client_secret, user_name, app_client_id)

    auth_data = {
        'USERNAME': user_name,
        'PASSWORD': password,
        'SECRET_HASH': SECRET_HASH,
    }
    provider_client = boto3.client(
        'cognito-idp',
        region_name='us-east-1',
        aws_access_key_id=LEGACY_AWS_ACCESS_KEY,
        aws_secret_access_key=LEGACY_AWS_SECRET_ACCESS_KEY,
    )

    resp = provider_client.admin_initiate_auth(
        UserPoolId=user_pool_id,
        ClientId=app_client_id,
        AuthFlow='ADMIN_NO_SRP_AUTH',
        AuthParameters=auth_data,
    )
    return resp['AuthenticationResult']['IdToken']

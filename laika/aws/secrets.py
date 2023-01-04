import base64
import json
import os

import boto3
from botocore.exceptions import ClientError

# Create a Secrets Manager client
REGION_NAME = "us-east-1"
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')

SESSION = boto3.session.Session(
    aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)
CLIENT = SESSION.client(service_name='secretsmanager', region_name=REGION_NAME)


def get_secret(secret_name):
    try:
        response = CLIENT.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        raise e
    else:
        # Decrypts secret using the associated KMS CMK.
        # Depending on whether the secret is a string or binary,
        # one of these fields will be populated.
        if 'SecretString' in response:
            secret_value = response['SecretString']
        else:
            secret_value = base64.b64decode(response['SecretBinary'])
        return json.loads(secret_value)

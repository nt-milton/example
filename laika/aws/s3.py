import os

import boto3

from laika.aws.secrets import REGION_NAME

LEGACY_AWS_ACCESS_KEY = os.getenv('LEGACY_AWS_ACCESS_KEY')
LEGACY_AWS_SECRET_ACCESS_KEY = os.getenv('LEGACY_AWS_SECRET_ACCESS_KEY')


# ---------- LEGACY ----------
legacy_s3_session = boto3.Session(
    region_name=REGION_NAME,
    aws_access_key_id=LEGACY_AWS_ACCESS_KEY,
    aws_secret_access_key=LEGACY_AWS_SECRET_ACCESS_KEY,
)

legacy_s3_client = legacy_s3_session.client('s3')
# ---------- LEGACY ----------


AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')

s3_session = boto3.Session(
    region_name=REGION_NAME,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)
s3_client = s3_session.client('s3')

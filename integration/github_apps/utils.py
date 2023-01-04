import io
import time
from typing import Dict

import boto3
import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from integration.github_apps.mapper import PullRequestDict, PullRequestRecord
from integration.settings import GITHUB_APP_BUCKET, GITHUB_APP_ID, GITHUB_APP_PEM

GITHUB_PAGE_SIZE = 100
GITHUB_APPS_ATTEMPTS = 3

SECONDARY_RATE_LIMIT_REGEX = r'.*secondary.*rate.*limit.*'


def get_jwt_token():
    client = boto3.client('s3')
    bytes_buffer = io.BytesIO()
    client.download_fileobj(
        Bucket=GITHUB_APP_BUCKET, Key=GITHUB_APP_PEM, Fileobj=bytes_buffer
    )
    byte_value = bytes_buffer.getvalue()
    pem_data = byte_value.decode()
    pem_key = pem_data.encode()
    pem_token = load_pem_private_key(pem_key, None, default_backend())
    current_time = int(time.time())
    jwt_token = jwt.encode(
        {
            # issued at time, 60 seconds in the past to allow for clock drift
            'iat': current_time - 60,
            # JWT expiration time (10 minute maximum)
            'exp': current_time + (10 * 60),
            # GitHub App's identifier
            'iss': GITHUB_APP_ID,
        },
        pem_token,
        'RS256',
    )
    return jwt_token.decode()


def get_pull_request_record(pr_visibility: str, **kwargs) -> PullRequestRecord:
    return (
        PullRequestRecord(**kwargs, pr_visibility='Private')
        if pr_visibility == 'Private'
        else PullRequestRecord(**kwargs, pr_visibility='Public')
    )


def get_pull_request_dict(pull_request: Dict) -> PullRequestDict:
    return PullRequestDict(
        number=pull_request.get('number', ''),
        updatedAt=pull_request.get('updatedAt', ''),
        weblink=pull_request.get('weblink', ''),
        title=pull_request.get('title', ''),
        target=pull_request.get('target', ''),
        source=pull_request.get('source', ''),
        state=pull_request.get('state', ''),
        reviewDecision=pull_request.get('reviewDecision', ''),
        reviews=pull_request.get('reviews', {}),
        createdAt=pull_request.get('createdAt', ''),
        author=pull_request.get('author', {}),
    )

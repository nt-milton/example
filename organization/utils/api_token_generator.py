import uuid
from datetime import datetime, timedelta, timezone
from typing import Tuple

import jwt
from django.contrib.auth.models import Group

from laika.settings import OPEN_API_SECRET
from organization.constants import DEFAULT_API_TOKEN_USAGE_TYPE
from organization.models import ApiTokenHistory
from user.models import User

DAYS_TO_EXPIRATION = 365


def generate_api_token(
    user: User,
    name: str,
    usage_type=DEFAULT_API_TOKEN_USAGE_TYPE,
    expiration_days=DAYS_TO_EXPIRATION,
) -> Tuple[str, ApiTokenHistory]:
    token_uuid = uuid.uuid4()
    api_user = (
        get_or_create_api_user(user)
        if usage_type == DEFAULT_API_TOKEN_USAGE_TYPE
        else user
    )
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=expiration_days)
    jwt_payload = {'exp': expires_at, 'email': api_user.email, 'uuid': str(token_uuid)}
    api_token = jwt.encode(jwt_payload, OPEN_API_SECRET).decode()
    token_record = ApiTokenHistory.objects.create(
        name=name,
        expires_at=expires_at,
        api_key=api_token,
        token_identifier=token_uuid,
        organization=user.organization,
        created_by=user,
        usage_type=usage_type,
    )
    return api_token, token_record


def get_or_create_api_user(user: User) -> User:
    organization = user.organization
    api_group = Group.objects.get(name='open_api_admin')
    org_name = organization.name.replace(' ', '')
    api_user_email = f'api+{org_name}@heylaika.com'
    api_user = User.objects.filter(
        organization=organization, groups__name=api_group.name
    )
    if api_user.exists():
        return api_user.first()

    user_data = {
        'first_name': 'Open API',
        'last_name': 'User',
        'email': api_user_email,
        'role': 'OrganizationViewer',
        'username': api_user_email,
    }
    api_user = User.objects.create(**user_data, organization=organization)
    api_user.groups.add(api_group)
    return api_user


def delete_excel_token(user: User):
    ApiTokenHistory.all_objects.filter(
        organization=user.organization, created_by=user, usage_type='EXCEL'
    ).delete()

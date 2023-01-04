import hashlib
import hmac
import logging
import os
from typing import List, Optional

import django.utils.timezone as timezone

from audit.constants import AUDITOR_ROLES
from audit.tasks import send_audit_invite_user_email
from laika.aws import cognito
from laika.aws.cognito import create_user, delete_cognito_users
from laika.constants import COGNITO, OKTA
from laika.okta.api import OktaApi
from laika.settings import ENVIRONMENT, LAIKA_BACKEND
from laika.utils.exceptions import ServiceException
from user.constants import (
    INVITATION_EXPIRATION_DAYS,
    NO_DAYS_LEFT,
    OKTA_GROUPS_NAMES,
    ROLE_ADMIN,
    ROLE_MEMBER,
    USER_STATUS,
)
from user.models import ROLES, User
from user.permissions import add_audit_user_to_group
from user.utils.invite_laika_user import send_invite
from vendor.models import OrganizationVendor, OrganizationVendorStakeholder

from .permissions import add_user_to_group

HELP_CENTER_SECRET_KEY = os.getenv('HELP_CENTER_SECRET_KEY')

OktaApi = OktaApi()

logger = logging.getLogger(__name__)


def get_user_by_email(organization_id, email, default=None):
    if not email:
        return default
    return User.objects.get(email=email, organization_id=organization_id)


def get_or_create_user_by_email(email, organization_id):
    if not email:
        return

    user, _ = User.objects.get_or_create(
        organization_id=organization_id,
        email=email,
        defaults={
            'role': '',
            'last_name': '',
            'first_name': '',
            'is_active': False,
            'username': '',
        },
    )
    return user


def create_auditor_credentials(user_data, sender='Admin'):
    email = user_data.get('email')

    if not user_data.get('permission') in AUDITOR_ROLES.values():
        raise ServiceException(f'Invalid permission for user {email}')

    create_user_data = {
        'role': user_data.get('permission'),
        'email': email,
        'last_name': user_data.get('last_name'),
        'first_name': user_data.get('first_name'),
    }

    cognito_user = create_user(create_user_data)

    user = User.objects.filter(email=email).first()

    user.username = cognito_user.get('username')
    user.save()

    add_audit_user_to_group(user)

    audit_firm = user_data.get('audit_firm', '')

    email_context = {
        'auditor': sender,
        'audit_firm': audit_firm,
        'username': user.email,
        'password': cognito_user.get('temporary_password'),
    }

    send_audit_invite_user_email.delay(user.email, email_context)


def get_admin_users_in_laika(organization_id: str) -> List[User]:
    roles = dict(ROLES)
    allow_roles_to_assign_user = [roles['SuperAdmin'], roles['OrganizationAdmin']]
    return User.objects.filter(
        organization_id=organization_id, role__in=allow_roles_to_assign_user
    )


def get_help_center_hash(user_id):
    key = bytes(HELP_CENTER_SECRET_KEY, 'utf-8')
    msg = bytes(user_id, 'utf-8')
    return hmac.new(key, msg, digestmod=hashlib.sha256).hexdigest()


def calculate_user_status(user: User) -> str:
    if user.invitation_sent is not None and not user.last_login:
        delta = timezone.now() - user.invitation_sent
        remaining_days = int(INVITATION_EXPIRATION_DAYS) - delta.days

        if remaining_days <= NO_DAYS_LEFT:
            return USER_STATUS['INVITATION_EXPIRED']

    if user.password_expired:
        return USER_STATUS['PASSWORD_EXPIRED']

    return (
        USER_STATUS['ACTIVE']
        if user.last_login is not None
        else USER_STATUS['PENDING_INVITATION']
    )


def manage_okta_user(
    user: User, should_invite=True
) -> tuple[Optional[User], Optional[str]]:
    try:
        okta_user = OktaApi.get_user_by_email(user.email)

        if okta_user:
            logger.info(f'Deleting okta user {okta_user}')
            OktaApi.delete_user(okta_user.id)

        user_groups = OKTA_GROUPS_NAMES[str(ENVIRONMENT)][LAIKA_BACKEND]
        okta_user, temporary_password = OktaApi.create_user(
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            login=user.email,
            organization=user.organization,
            user_groups=user_groups,
        )

        user.username = okta_user.id
        user.is_active = True
        user.invitation_sent = timezone.now()
        user.password_expired = False
        user.last_login = None
        user.save()

        add_user_to_group(user)

        if should_invite:
            send_email_invite(user, temporary_password, OKTA)

        return user, temporary_password
    except Exception as e:
        logger.exception(
            'There was a problem creating okta user with'
            f'id {user.id} credentials and invite. Error: {e}'
        )
        OktaApi.delete_user(okta_user.id)
        user.is_active = False
        user.save()

        return None, None


def manage_cognito_user(
    user: User, should_invite=True
) -> tuple[Optional[User], Optional[str]]:
    try:
        cognito_user = cognito.get_user(user.username)
        if cognito_user:
            logger.info(f'Deleting cognito user {cognito_user}')
            delete_cognito_users([user.email])

        created_user = create_cognito_user(user)

        user.username = created_user.get('username')
        user.is_active = True
        user.invitation_sent = timezone.now()
        user.password_expired = False
        user.last_login = None
        user.save()

        add_user_to_group(user)

        if should_invite:
            send_email_invite(user, created_user.get('temporary_password'), COGNITO)

        return user, created_user.get('temporary_password')
    except Exception as e:
        logger.exception(
            'There was a problem creating cognito user with'
            f'id {user.id} credentials and invite. Error: {e}'
        )
        delete_cognito_users([user.email])
        user.is_active = False
        user.save()

        return None, None


def send_email_invite(user: User, temporary_password: str, idp: str):
    email_context = {
        'name': 'Admin',
        'email': user.email,
        'password': temporary_password,
        'role': user.role,
        'idp': idp,
    }

    logger.info(f'Trying to send email invite to: {user.email}')
    send_invite(email_context)


def create_cognito_user(user):
    create_user_data = {
        'role': ROLE_MEMBER if user.role != ROLE_ADMIN else user.role,
        'email': user.email,
        'last_name': user.last_name,
        'first_name': user.first_name,
        'organization_id': user.organization.id,
        'tier': user.organization.tier,
        'organization_name': user.organization.name,
    }

    return create_user(create_user_data)


def assign_user_to_organization_vendor_stakeholders(
    organization_vendor: OrganizationVendor, user: User
):
    sort_index = organization_vendor.internal_organization_stakeholders.count() + 1
    return OrganizationVendorStakeholder.objects.create(
        sort_index=sort_index,
        organization_vendor=organization_vendor,
        stakeholder=user,
    )

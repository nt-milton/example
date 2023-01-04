import logging
from typing import Dict, Union

import user.errors as errors
from laika.utils.exceptions import ServiceException
from organization.models import Organization
from user.constants import USER_ROLES
from user.models import DISCOVERY_STATE_CONFIRMED, User
from user.permissions import add_user_to_group

logger = logging.getLogger(__name__)


def invite_partial_user_m(
    organization: Organization, user_input: Dict, connection_id: Union[int, None] = None
) -> Dict:
    user_org = Organization.objects.get(pk=user_input.get('organization_id'))
    email = user_input.get('email')
    role = user_input.get('role') or USER_ROLES['VIEWER']

    if user_org != organization:
        raise ServiceException(errors.NO_ORGANIZATION_USER)

    if role not in USER_ROLES.values():
        raise ServiceException('Invalid role for user')

    manager_email = user_input.get('manager_email')
    manager = None
    if manager_email:
        manager = User.objects.filter(
            email=manager_email, organization=user_org
        ).first()
    user, created = User.objects.update_or_create(
        email=email,
        organization=user_org,
        defaults={
            'last_name': user_input.get('last_name'),
            'first_name': user_input.get('first_name'),
            'phone_number': user_input.get('phone_number'),
            'title': user_input.get('title'),
            'department': user_input.get('department'),
            'employment_type': user_input.get('employment_type'),
            'employment_subtype': user_input.get('employment_subtype'),
            'start_date': user_input.get('start_date'),
            'end_date': user_input.get('end_date'),
            'employment_status': user_input.get('employment_status', ''),
            'connection_account_id': connection_id,
            'manager': manager,
            'finch_uuid': user_input.get('finch_uuid'),
            'discovery_state': user_input.get(
                'discovery_state', DISCOVERY_STATE_CONFIRMED
            ),
        },
    )
    if created:
        user.role = role
        user.is_active = False
        add_user_to_group(user)
        user.save()
        _log_created_user_message(
            user=user, organization=organization, connection_id=connection_id
        )

    return {'data': user}


def _log_created_user_message(
    user: User, organization: Organization, connection_id: Union[int, None]
) -> None:
    default_msg = (
        f'Partial user invited with ID: {user.id} on organization {organization.id}'
    )

    default_msg = (
        f'Connection account {connection_id} - {default_msg}'
        if connection_id
        else default_msg
    )

    logger.info(default_msg)

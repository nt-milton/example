import logging
from datetime import date, timedelta
from typing import Any, Callable, Dict, Iterable, List, Union

from address.models import Address
from alert.constants import ALERT_TYPES
from alert.models import PeopleDiscoveryAlert
from laika.aws.cognito import enable_cognito_users
from organization.models import ACTIVE, Organization, OrganizationLocation
from program.utils.alerts import create_alert
from user.models import (
    DISCOVERY_STATE_CONFIRMED,
    DISCOVERY_STATE_NEW,
    EMPLOYMENT_STATUS_ACTIVE,
    EMPLOYMENT_STATUS_INACTIVE,
    User,
)
from user.utils.invite_partial_user import invite_partial_user_m

from ..log_utils import logger_extra
from ..models import ConnectionAccount

JSONType = Dict[str, Any]
logger = logging.getLogger(__name__)

EMAIL_NOT_FOUND = 'not_found'
SKIP_USERS = [
    'payroll@tryfinch.com',
    'payroll@heylaika.com',
    'integrations@pave.com',
    'benefits@guideline.com',
    'no-reply@tryfinch.com',
    'ops@kruzeconsulting.com',
]


def save_locations(
    locations: Iterable[JSONType], organization: Organization, map_location: Callable
) -> None:
    requires_hq = not OrganizationLocation.objects.filter(
        organization=organization, hq=True
    ).exists()
    for idx, loc in enumerate(locations):
        hq = dict(hq=True) if idx == 0 and requires_hq else None
        address = map_location(loc)
        address, _ = Address.objects.update_or_create(**address)
        OrganizationLocation.objects.update_or_create(
            organization=organization, address=address, defaults=hq
        )


def integrate_people_discovery(
    connection_account: ConnectionAccount,
) -> None:
    organization = connection_account.organization
    two_hours_ago = date.today() - timedelta(hours=2)
    new_users_quantity = User.objects.filter(
        organization=organization,
        discovery_state=DISCOVERY_STATE_NEW,
        date_joined__gt=two_hours_ago,
    ).count()
    if new_users_quantity > 0:
        receivers = User.objects.filter(
            organization=organization,
            role__in=['OrganizationMember', 'OrganizationAdmin', 'SuperAdmin'],
        )
        from integration.slack.implementation import send_alert_to_slack

        from ..slack.types import SlackAlert

        alert_type = ALERT_TYPES['PEOPLE_DISCOVERY']
        slack_alert = SlackAlert(
            alert_type=alert_type,
            quantity=new_users_quantity,
            receiver=receivers.first(),
        )
        send_alert_to_slack(slack_alert)
        logger.info(
            f'Connection account {connection_account.id} - '
            f'Slack message sent with #{new_users_quantity} of people '
            'discovered.'
        )
        for receiver in receivers:
            create_alert(
                room_id=organization.id,
                receiver=receiver,
                alert_type=alert_type,
                alert_related_model=PeopleDiscoveryAlert,
                alert_related_object={'quantity': new_users_quantity},
            )
            logger.info(
                f'Connection account {connection_account.id} - '
                f'Alert sent with #{new_users_quantity} people '
                f'discovered to user {receiver.id}.'
            )


def existing_finch_to_laika_email(finch_id_by_email: Dict[str, str]) -> Dict[Any, User]:
    uuids_by_emails = finch_id_by_email.values()
    existing_users_by_uuids = User.objects.filter(finch_uuid__in=uuids_by_emails)
    finch_to_laika_email = {}
    for existing_user in existing_users_by_uuids:
        email = existing_user.email
        is_duplicated = existing_user.finch_uuid in finch_to_laika_email
        if is_duplicated and email not in finch_id_by_email:
            # for duplicate records integration email has priority
            continue
        finch_to_laika_email[existing_user.finch_uuid] = email
    return finch_to_laika_email


def update_finch_uuid(finch_id_by_email: Dict[str, str]) -> None:
    user_emails = finch_id_by_email.keys()
    users_to_update = User.objects.filter(
        email__in=user_emails, finch_uuid__isnull=True
    )

    for user_to_update in users_to_update:
        user_to_update.finch_uuid = finch_id_by_email.get(user_to_update.email)

    User.objects.bulk_update(users_to_update, ['finch_uuid'])


def update_manager_id(external_to_laika, raw_people, get_manager_id):
    for raw_person in raw_people:
        person_manager_id = get_manager_id(raw_person)
        person_id = external_to_laika.get(raw_person.get('id'))
        if person_manager_id and person_id:
            manager_id = external_to_laika.get(person_manager_id)
            if not manager_id:
                logger.info(
                    f'Person (Manager) with ID {person_manager_id} '
                    'does not exist in our records. '
                    f'Failed updating manager for person {person_id}'
                )
                continue

            User.objects.filter(id=person_id).update(manager_id=manager_id)
            logger.info(f'Person ID {person_id} updated with manager ID {manager_id}')


def require_activation(person: Dict[str, Any], organization: Organization) -> bool:
    if person.get('employment_status') != EMPLOYMENT_STATUS_ACTIVE:
        return False
    return (
        User.objects.exclude(username='')
        .filter(organization=organization, is_active=False, email=person.get('email'))
        .exists()
    )


def disable_missing_people(
    connection_account: ConnectionAccount, user_ids: Iterable[int]
) -> None:
    missing_people = User.objects.filter(connection_account=connection_account).exclude(
        id__in=user_ids
    )
    logger.info(
        f'Connection account {connection_account.id} - '
        f'Missing people: {list(missing_people)}'
    )

    missing_people.update(employment_status=EMPLOYMENT_STATUS_INACTIVE)


def integrate_and_invite_people(
    raw_people: List,
    map_to_laika: Callable,
    connection_account: ConnectionAccount,
    source_system: str,
):
    connection_id = connection_account.id
    organization = connection_account.organization

    external_to_laika = {}
    laika_people = []
    finch_uuids_by_emails: Dict[Any, Any] = {}
    # If a user already has an email it should not be updated
    for raw_person in raw_people:
        laika_person = map_to_laika(raw_person)
        person_email = laika_person.get('email')
        if person_email and person_email != EMAIL_NOT_FOUND:
            logger.info(
                f'Connection account {connection_id} - '
                f'{source_system} mapped user: {laika_person}'
            )
            laika_people.append(laika_person)
            finch_uuids_by_emails[laika_person.get('email')] = laika_person.get(
                'finch_uuid'
            )

    update_finch_uuid(finch_uuids_by_emails)

    existing_email_by_uuid = existing_finch_to_laika_email(finch_uuids_by_emails)

    for user_to_invite in laika_people:
        if user_to_invite.get('email') in SKIP_USERS:
            continue
        finch_uuid = user_to_invite.get('finch_uuid')
        existing_email = existing_email_by_uuid.get(finch_uuid)
        if existing_email and user_to_invite.get('email') != existing_email:
            email = user_to_invite.get('email')
            logger.info(
                f'Connection account {connection_account.id} - '
                f'Replacing user with email {email} '
                f'with existing email {existing_email} on finch '
                f'uuid {finch_uuid}'
            )
            user_to_invite['email'] = existing_email

        populate_discovery_state(organization, user_to_invite)
        user = invite_partial_user_m(
            organization, user_to_invite, connection_id=connection_account.id
        )['data']
        if require_activation(user_to_invite, organization):
            logger.info(
                f'Connection account {connection_id} - Reactivating user {user.id}.'
            )
            enable_cognito_users([user.email])
            user.is_active = True
            user.save()
        external_to_laika[finch_uuid] = user.id

    user_ids = external_to_laika.values()
    logger.info(
        f'Connection account {connection_id} - User IDs to be updated: {user_ids}'
    )
    # OP-364: Remove the disabled user. Read the ticket comments for more
    # context
    # disable_active_users(connection_account, user_ids)
    disable_missing_people(connection_account, user_ids)

    return external_to_laika


def populate_discovery_state(organization: Organization, user_to_invite: dict):
    default_discovery_state = (
        DISCOVERY_STATE_NEW
        if organization.state == ACTIVE
        else DISCOVERY_STATE_CONFIRMED
    )
    existing_discovery_state = (
        User.objects.filter(
            email=user_to_invite.get('email'), organization=organization
        )
        .values_list('discovery_state', flat=True)
        .first()
    )
    user_to_invite['discovery_state'] = (
        existing_discovery_state or default_discovery_state
    )


def _get_individual_details(individual: JSONType) -> Dict:
    return {
        'id': individual.get('id'),
        'first_name': individual.get('first_name'),
        'last_name': individual.get('last_name'),
    }


def does_individual_has_work_email(individual: JSONType) -> bool:
    if not individual.get('emails'):
        details = _get_individual_details(individual=individual)
        message = f'Individual {str(details)} does not have emails!.'
        logger.info(logger_extra(message))
        return False

    work_emails = [
        email['data'] for email in individual['emails'] if email['type'] == 'work'
    ]

    def _has_work_email(individual_work_emails: List) -> bool:
        return len(individual_work_emails) > 0

    has_work_email: bool = _has_work_email(work_emails)
    if not has_work_email:
        details = _get_individual_details(individual=individual)
        message = f"Individual {str(details)} doesn't have WORK email."
        logger.info(logger_extra(message))

    return has_work_email


def get_individual_work_phone_number(
    individual: JSONType, **kwargs
) -> Union[str, None]:
    if not individual.get('phone_numbers'):
        details = _get_individual_details(individual=individual)
        message = f"Individual {str(details)} doesn't have phone numbers!."
        logger.info(logger_extra(message, **kwargs))
        return None

    work_phones = [
        phone['data']
        for phone in individual['phone_numbers']
        if phone['type'] == 'work'
    ]

    if len(work_phones) == 0:
        details = _get_individual_details(individual=individual)
        message = f"Individual {str(details)} doesn't have WORK phone number."
        logger.info(logger_extra(message, **kwargs))
        return None

    return work_phones[0]


def update_raw_people(raw_people: List[Dict], work_individual_ids: List) -> List[Dict]:
    return [person for person in raw_people if person.get('id') in work_individual_ids]

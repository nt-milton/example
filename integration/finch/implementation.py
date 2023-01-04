import logging
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

import cryptography

from integration.account import integrate_account
from integration.integration_utils.people_utils import (
    does_individual_has_work_email,
    get_individual_work_phone_number,
    integrate_and_invite_people,
    integrate_people_discovery,
    save_locations,
    update_manager_id,
    update_raw_people,
)
from laika.aws.cognito import disable_cognito_users
from organization.models import Organization
from user.models import EMPLOYMENT_STATUS_ACTIVE, User

from ..encryption_utils import decrypt_value, encrypt_value
from ..log_utils import connection_data, logger_extra
from ..models import ConnectionAccount
from . import http_client

logger = logging.getLogger(__name__)
JSONType = dict[str, Any]

EMAIL_NOT_FOUND = 'not_found'
N_RECORDS = {'people': 0, 'people_discovered': 0}

FINCH_SYSTEM = 'Finch'


def encrypt_access_token(response: dict) -> dict:
    return {'access_token': encrypt_value(response['access_token'])}


def connect(connection_account: ConnectionAccount) -> None:
    with connection_account.connection_error():
        code = connection_account.configuration_state.get('credentials')
        response = http_client.get_token(code)
        connection_account.authentication = encrypt_access_token(response)
        connection_account.save()
        integrate_organization(response['access_token'], connection_account)


def _is_field_valid_in_company(
    organization: Organization, company_response: JSONType, field: str
) -> bool:
    if field not in company_response or not company_response[field]:
        logger.info(
            f'Invalid field {field} in company response: {company_response} '
            f'for organization: {organization.id}'
        )
        return False
    return True


def integrate_organization(
    access_token: str, connection_account: ConnectionAccount
) -> None:
    organization = connection_account.organization
    company = http_client.read_company(access_token)
    if company:
        if _is_field_valid_in_company(organization, company, 'legal_name'):
            organization.name = company['legal_name']
            organization.legal_name = company['legal_name']
            organization.save()

        if _is_field_valid_in_company(organization, company, 'locations'):
            save_locations(company['locations'], organization, map_location)


def _update_numbers_of_records(connection_account: ConnectionAccount) -> Dict:
    N_RECORDS['people'] = connection_account.people_amount
    N_RECORDS['people_discovered'] = connection_account.discovered_people_amount
    return N_RECORDS


def run(connection_account: ConnectionAccount) -> None:
    with connection_account.connection_attempt():
        access_token = connection_account.authentication['access_token']
        try:
            decrypt_value(access_token)
        except cryptography.fernet.InvalidToken:
            connection_account.authentication['access_token'] = encrypt_value(
                access_token
            )
        provider = connection_account.integration.vendor.name
        _integrate_company(connection_account)
        integrate_people_discovery(connection_account)
        integrate_account(
            connection_account=connection_account,
            source_system=provider,
            records_dict=_update_numbers_of_records(connection_account),
        )


def _integrate_company(connection_account: ConnectionAccount) -> None:
    access_token = decrypt_value(connection_account.authentication['access_token'])
    integrate_people(access_token, connection_account)


def integrate_people(
    access_token: str, connection_account: ConnectionAccount
) -> Dict[str, int]:
    valid_domains = connection_account.configuration_state.get('validDomains', [])
    raw_people = http_client.read_directory(access_token)['individuals']
    all_people_ids = [person['id'] for person in raw_people]
    individuals = load_individuals(access_token, all_people_ids, valid_domains)
    individuals_ids = list(individuals.keys())
    employments = load_employments(access_token, individuals_ids)
    if len(all_people_ids) != len(individuals_ids):
        logger.info(
            f'Connection account {connection_account.id} - '
            'Updating raw people due difference on ids by emails. '
            f'All people {len(all_people_ids)} vs Individuals with '
            f'work email {len(individuals_ids)}'
        )
        raw_people = update_raw_people(raw_people, individuals_ids)

    organization = connection_account.organization
    map_to_laika = build_map_person(
        organization_id=organization.id,
        individuals=individuals,
        employments=employments,
        connection_account=connection_account,
    )

    external_to_laika = integrate_and_invite_people(
        raw_people=raw_people,
        map_to_laika=map_to_laika,
        connection_account=connection_account,
        source_system=FINCH_SYSTEM,
    )
    update_manager_id(external_to_laika, raw_people, manager_id)
    return external_to_laika


def disable_active_users(
    connection_account: ConnectionAccount, user_ids: Iterable[int]
) -> None:
    disable_users = User.objects.filter(
        connection_account=connection_account, is_active=True
    ).exclude(id__in=user_ids, employment_status=EMPLOYMENT_STATUS_ACTIVE)
    logger.info(f'Disabling users: {list(disable_users)}')
    emails = [user.email for user in disable_users]
    disable_cognito_users(emails)
    disable_users.update(is_active=False)


def load_individuals(
    access_token: str, ids: Iterable[str], valid_domains: list
) -> JSONType:
    individuals = http_client.read_individual_details(access_token, ids)
    return {
        detail['individual_id']: detail['body']
        for detail in individuals['responses']
        if does_individual_has_work_email(detail['body'])
        and does_email_has_valid_domain(detail['body'], valid_domains)
    }


def does_email_has_valid_domain(individual: dict, valid_domains: list) -> bool:
    if not individual.get('emails'):
        return False

    if not valid_domains:
        return True

    emails = [
        email['data'] for email in individual['emails'] if email['type'] == 'work'
    ]
    if emails[0]:
        email = emails[0]
        current_domain = email.split('@')[1]
        return current_domain in valid_domains
    return False


def load_employments(access_token: str, ids: Iterable[str]) -> JSONType:
    employments: Dict = http_client.read_employments(access_token, ids)

    employment_responses: List[Dict] = employments.get('responses', [])

    if len(employment_responses) > 0 and employment_responses[0].get('body', {}).get(
        'income'
    ):
        # Notify by an alert if the income data is present, there
        # is already a feature flag in finch to avoid return it
        logger.warning(logger_extra('🔥 INCOME object is present on Finch response'))

    return {emp['individual_id']: emp['body'] for emp in employment_responses}


def map_location(location: JSONType) -> Dict[str, str]:
    return dict(
        street1=location.get('line1') or '',
        street2=location.get('line2') or '',
        city=location.get('city') or '',
        state=location.get('state') or '',
        country=location.get('country') or '',
        zip_code=location.get('postal_code') or '',
    )


def _get_employment_dates(
    employment: JSONType,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    start_date, end_date = None, None

    def _format_date(date_to_format: str) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(date_to_format)
        except ValueError:
            logger.warning(f'Error formatting the date: {date_to_format}')
            return None

    if employment.get('start_date'):
        start_date = _format_date(employment['start_date'])
    if employment.get('end_date'):
        end_date = _format_date(employment['end_date'])

    return start_date, end_date


def build_map_person(
    organization_id: int,
    individuals: Dict[str, JSONType],
    employments: Dict[str, JSONType],
    connection_account: ConnectionAccount,
) -> Callable[[JSONType], Dict[str, Any]]:
    data = connection_data(connection_account)

    def map_person(person: JSONType) -> Dict[str, Any]:
        individual = individuals[person['id']]
        employment = employments[person['id']]
        start_date, end_date = _get_employment_dates(employment)
        return dict(
            organization_id=organization_id,
            first_name=person.get('first_name'),
            last_name=person.get('last_name'),
            email=work_email(individual).lower(),
            title=employment.get('title', ''),
            employment_type=employment.get('employment', {}).get('type', ''),
            employment_subtype=employment.get('employment', {}).get('subtype', ''),
            department=department_name(person),
            employment_status=User.map_employment_status(
                employment.get('is_active', False)
            ),
            start_date=start_date,
            end_date=end_date,
            phone_number=phone_number(individual, **data),
            finch_uuid=person['id'],
        )

    return map_person


def manager_id(person: JSONType) -> Optional[str]:
    manager = person.get('manager')
    if not manager:
        return None
    return manager['id']


def work_email(individual: JSONType) -> str:
    if not does_individual_has_work_email(individual):
        return EMAIL_NOT_FOUND

    default_email, *_ = individual['emails']
    work_emails = (
        email['data'] for email in individual['emails'] if email['type'] == 'work'
    )
    return next(work_emails, default_email['data'])


def department_name(person: JSONType) -> Optional[str]:
    department = person.get('department')
    return None if not department else department['name']


def phone_number(individual: JSONType, **kwargs: Dict) -> Union[str, None]:
    return get_individual_work_phone_number(individual, **kwargs)

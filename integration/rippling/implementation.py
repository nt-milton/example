import logging
from typing import Any, Dict, Optional

from integration.account import get_integration_laika_objects, integrate_account
from integration.integration_utils.people_utils import (
    integrate_and_invite_people,
    integrate_people_discovery,
    save_locations,
    update_manager_id,
)
from objects.system_types import ACCOUNT, DEVICE, USER
from organization.models import Organization
from user.models import User as UserModel

from ..exceptions import ConfigurationError, ConnectionAlreadyExists
from ..log_utils import connection_data
from ..models import ConnectionAccount
from ..store import Mapper, update_laika_objects
from ..utils import resolve_laika_object_types
from .mapper import build_mapper, map_device_response_to_laika_object
from .rest_client import (
    create_access_token,
    create_refresh_token,
    get_company,
    get_current_user,
    get_devices_report,
    get_employees,
)

RIPPLING_SYSTEM = 'Rippling'
logger = logging.getLogger(__name__)
JSONType = Dict[str, Any]

N_RECORDS = get_integration_laika_objects(RIPPLING_SYSTEM)


def perform_refresh_token(connection_account: ConnectionAccount):
    data = connection_data(connection_account)
    refresh_token = connection_account.authentication['refresh_token']
    access_token, refresh_token = create_access_token(refresh_token, **data)
    if not access_token:
        logger.warning(
            f'Error refreshing token for {RIPPLING_SYSTEM} '
            f'connection account {connection_account.id}'
        )


def callback(code, redirect_uri, connection_account: ConnectionAccount):
    if not code:
        raise ConfigurationError.denial_of_consent()

    data = connection_data(connection_account)
    response = create_refresh_token(code, redirect_uri, **data)
    organization = connection_account.organization
    resolve_laika_object_types(organization, [ACCOUNT, USER, DEVICE])
    connection_account.authentication = response
    connection_account.authentication['data'] = add_current_user(connection_account)
    connection_account.configuration_state['launchedOauth'] = True
    connection_account.save()
    integrate_organization(connection_account)
    return connection_account


def _update_numbers_of_records(connection_account: ConnectionAccount) -> Dict:
    N_RECORDS['people'] = connection_account.people_amount
    N_RECORDS['people_discovered'] = connection_account.discovered_people_amount
    return N_RECORDS


def run(connection_account: ConnectionAccount) -> None:
    with connection_account.connection_attempt():
        raise_if_duplicate(connection_account)
        integrate_users(connection_account)
        integrate_people(connection_account)
        integrate_people_discovery(connection_account)
        integrate_devices(connection_account)

        integrate_account(
            connection_account=connection_account,
            source_system=RIPPLING_SYSTEM,
            records_dict=_update_numbers_of_records(connection_account),
        )


def raise_if_duplicate(connection_account: ConnectionAccount):
    data = connection_account.authentication.get('data')
    exists = (
        ConnectionAccount.objects.actives(
            authentication__data=data, organization=connection_account.organization
        )
        .exclude(id=connection_account.id)
        .exists()
    )
    if exists:
        raise ConnectionAlreadyExists()


def add_current_user(connection_account: ConnectionAccount):
    data = connection_data(connection_account)
    access_token = connection_account.authentication.get('access_token')
    return get_current_user(access_token, **data)


def integrate_users(connection_account: ConnectionAccount):
    data = connection_data(connection_account)
    access_token = get_access_token(connection_account)
    users = get_employees(access_token)
    company = get_company(access_token, **data)
    user_mapper = Mapper(
        map_function=build_mapper(company), keys=['Id'], laika_object_spec=USER
    )
    update_laika_objects(connection_account, user_mapper, users)


def integrate_devices(connection_account: ConnectionAccount):
    data = connection_data(connection_account)
    access_token = get_access_token(connection_account)
    devices = get_devices_report(access_token, **data)
    device_mapper = Mapper(
        map_function=map_device_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=DEVICE,
    )
    update_laika_objects(connection_account, device_mapper, devices)


def get_access_token(connection_account: ConnectionAccount):
    data = connection_data(connection_account)
    refresh_token = connection_account.authentication['refresh_token']
    access_token, refresh_token = create_access_token(refresh_token, **data)
    connection_account.authentication['refresh_token'] = refresh_token
    connection_account.save()
    return access_token


def integrate_organization(connection_account: ConnectionAccount) -> None:
    data = connection_data(connection_account)
    access_token = connection_account.authentication.get('access_token')
    company = get_company(access_token, **data)
    organization = connection_account.organization
    if _is_field_valid_in_company(organization, company, 'legalName'):
        organization.name = company.get('legalName', '')
        organization.legal_name = company.get('legalName', '')
        organization.save()

    if _is_field_valid_in_company(organization, company, 'workLocations'):
        locations = company.get('workLocations', [])
        save_locations(locations, organization, map_location)


def _is_field_valid_in_company(
    organization: Organization, company_response: JSONType, field: str
) -> bool:
    if field not in company_response or not company_response[field]:
        logger.warning(
            f'Invalid field {field} in company response: {company_response} '
            f'for organization: {organization.id}'
        )
        return False
    return True


def map_location(location: JSONType) -> Dict[str, str]:
    address = location.get('address', {})
    return dict(
        street1=address.get('streetLine1') or '',
        street2=address.get('streetLine2') or '',
        city=address.get('city') or '',
        state=address.get('state') or '',
        country=address.get('country') or '',
        zip_code=address.get('zip') or '',
    )


def integrate_people(connection_account: ConnectionAccount) -> Dict[str, int]:
    valid_domains = connection_account.configuration_state.get('validDomains', [])
    access_token = get_access_token(connection_account)
    raw_people = get_employees(access_token)
    filtered_people = get_filtered_people(raw_people, valid_domains)
    organization = connection_account.organization
    map_to_laika = build_map_person(organization.id)

    external_to_laika = integrate_and_invite_people(
        raw_people=filtered_people,
        map_to_laika=map_to_laika,
        connection_account=connection_account,
        source_system=RIPPLING_SYSTEM,
    )
    update_manager_id(external_to_laika, raw_people, manager_id)
    return external_to_laika


def get_filtered_people(people: list, valid_domains: list) -> list:
    filtered_people = []
    if not valid_domains:
        return people
    for person in people:
        email = person.get('workEmail')
        domain = email.split('@')[1] if email else None
        if domain in valid_domains:
            filtered_people.append(person)
    return filtered_people


def build_map_person(organization_id: str):
    def map_person(person):
        return dict(
            organization_id=organization_id,
            first_name=person.get('firstName', ''),
            last_name=person.get('lastName', ''),
            email=person.get('workEmail', ''),
            title=person.get('title', ''),
            employment_type=person.get('employmentType', ''),
            department=person.get('department', ''),
            employment_status=get_employment_status(person.get('roleState')),
            end_date=person.get('endDate'),
            phone_number=person.get('phoneNumber', ''),
            finch_uuid=person.get('id'),
        )

    return map_person


def get_employment_status(status: str):
    employment_status = True
    if status == 'TERMINATED':
        employment_status = False
    return UserModel.map_employment_status(employment_status)


def manager_id(person: JSONType) -> Optional[str]:
    return person.get('manager', None)

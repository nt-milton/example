import logging

from integration.store import Mapper, update_laika_objects
from integration.utils import resolve_laika_object_types
from objects.system_types import ACCOUNT, BACKGROUND_CHECK

from ..account import get_integration_laika_objects, integrate_account
from ..encryption_utils import get_decrypted_or_encrypted_value
from ..exceptions import ConnectionAlreadyExists
from ..models import ConnectionAccount
from .constants import INVALID_VETTY_API_KEY
from .mapper import _map_background_checks
from .rest_client import (
    get_applicants,
    get_applicants_per_page,
    get_packages,
    get_screening,
)

logger = logging.getLogger(__name__)

VETTY_SYSTEM = 'Vetty'
N_RECORDS = get_integration_laika_objects(VETTY_SYSTEM)


def run(connection_account: ConnectionAccount):
    with connection_account.connection_attempt():
        raise_if_duplicate(connection_account)
        api_key = get_api_key(connection_account)
        organization = connection_account.organization
        resolve_laika_object_types(organization, [ACCOUNT, BACKGROUND_CHECK])
        integrate_background_checks(connection_account, api_key)
        integrate_account(connection_account, VETTY_SYSTEM, N_RECORDS)


def connect(connection_account: ConnectionAccount):
    with connection_account.connection_error(error_code=INVALID_VETTY_API_KEY):
        if 'credentials' in connection_account.configuration_state:
            validate_api_key(connection_account)


def validate_api_key(connection_account: ConnectionAccount):
    api_key = get_api_key(connection_account)
    get_applicants_per_page(api_key, 0)


def raise_if_duplicate(connection_account):
    api_key = get_api_key(connection_account)
    vetty_connection_accounts: list[
        ConnectionAccount
    ] = ConnectionAccount.objects.filter(
        organization=connection_account.organization,
        integration=connection_account.integration,
    ).exclude(
        id=connection_account.id
    )
    for vetty_connection_account in vetty_connection_accounts:
        api_key_decrypted = get_decrypted_or_encrypted_value(
            'apiKey', vetty_connection_account
        )
        if api_key_decrypted == api_key:
            raise ConnectionAlreadyExists()


def integrate_background_checks(connection_account: ConnectionAccount, api_key: str):
    background_checks = get_background_checks(connection_account, api_key)
    background_checks_mapper = Mapper(
        map_function=_map_background_checks,
        keys=['Id'],
        laika_object_spec=BACKGROUND_CHECK,
    )
    update_laika_objects(
        connection_account, background_checks_mapper, background_checks
    )


def get_background_checks(connection_account: ConnectionAccount, api_key: str):
    applicants = get_applicants(api_key)
    packages_list = get_packages(api_key)
    packages = make_packages_dict(packages_list)
    background_checks = []
    for applicant in applicants:
        applicant_id = applicant['id']
        screening = get_screening(api_key, applicant_id)
        if screening:
            package_id = screening.get('package_id')
            package_info = packages[package_id]
            background_check = {
                'applicant': applicant,
                'package': package_info,
                'status': screening['status'],
                'id': screening['id'],
            }
            background_checks.append(background_check)
        else:
            logger.warning(
                f'Connection account {connection_account.id} - '
                f'No screening found for applicant: {applicant_id}'
            )
    return background_checks


def make_packages_dict(packages: list) -> dict:
    packages_dict = {}
    for package in packages:
        package_id = package.pop('id')
        packages_dict[package_id] = package
    return packages_dict


def get_api_key(connection_account: ConnectionAccount):
    return get_decrypted_or_encrypted_value('apiKey', connection_account)

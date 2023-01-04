import logging
import time
from copy import deepcopy
from typing import List, Tuple

from cryptography.fernet import InvalidToken

from integration.account import get_integration_laika_objects, integrate_account
from integration.encryption_utils import decrypt_value, encrypt_value
from integration.exceptions import (
    ConfigurationError,
    ConnectionAlreadyExists,
    ConnectionResult,
)
from integration.github_apps.constants import (
    ORGANIZATION_NOT_INSTALLED,
    ORGANIZATION_REQUIRED,
    PERSONAL_ACCOUNT_NOT_ALLOWED,
)
from integration.github_apps.mapper import (
    GithubUser,
    RepositoryRecord,
    TeamMembers,
    map_pull_requests_to_laika_object,
    map_repository_to_laika_object,
    map_users_to_laika_object,
)
from integration.github_apps.rest_client import (
    GithubOrganization,
    get_installation_access_token,
    get_organization,
    get_repository_pull_requests_and_next_page,
    get_user,
    read_all_organization_members_by_teams,
    read_all_organization_users,
    read_all_repositories,
)
from integration.github_apps.utils import get_jwt_token
from integration.log_utils import logger_extra
from integration.models import ConnectionAccount
from integration.store import Mapper, clean_up_by_criteria, update_laika_objects
from integration.utils import calculate_date_range, iso_format, wizard_error
from objects.system_types import PULL_REQUEST, REPOSITORY, USER

TOKEN_EXPIRATION = 'token_expiration'
GITHUB_SYSTEM = 'GitHub Apps'
USER_TYPE = 'User'

NO_INSTALLATION_FOUND = None
logger = logging.getLogger(__name__)
N_RECORDS = get_integration_laika_objects(GITHUB_SYSTEM)


def _token_expired(connection_account: ConnectionAccount) -> bool:
    token_expiration = connection_account.authentication.get(TOKEN_EXPIRATION, 0)
    return token_expiration < int(time.time())


def build_fetch_by_time(connection_account: ConnectionAccount):
    installation = connection_account.authentication.get('installation')

    def next_token():
        if _token_expired(connection_account):
            _reload_access_tokens_by_apps(connection_account)
        return _get_decrypted_installation_field(installation, 'access_token')

    return next_token


def get_installation(
    connection_account: ConnectionAccount,
) -> GithubOrganization:
    installation = connection_account.authentication['installation']
    login = _get_decrypted_installation_field(installation, 'login')
    return GithubOrganization(
        login,
        build_fetch_by_time(connection_account),
    )


def _get_pull_requests_mapper():
    return Mapper(
        map_function=map_pull_requests_to_laika_object,
        keys=['Key', 'Organization'],
        laika_object_spec=PULL_REQUEST,
    )


def _get_new_installation_app(connection_account: ConnectionAccount) -> str:
    organization = connection_account.credentials.get('organization')
    if not organization:
        logger.warning(logger_extra('Organization is required.'))
        raise wizard_error(connection_account, ORGANIZATION_REQUIRED)

    return organization


def connect(connection_account: ConnectionAccount):
    def connect_new_application():
        connection_credentials: dict = connection_account.credentials
        if not connection_credentials:
            raise ConfigurationError.bad_client_credentials()

        new_application = _get_new_installation_app(connection_account)
        logger.info(logger_extra(f'Adding app {new_application}'))

        installation: dict = _get_customer_installed_apps(
            connection_account, new_application
        )

        connection_account.authentication['installation'] = installation

    with connection_account.connection_error():
        connect_new_application()


def run(connection_account: ConnectionAccount):
    run_by_lo_types(connection_account, [])


def run_by_lo_types(connection_account: ConnectionAccount, lo_types: list[str]):
    with connection_account.connection_attempt():
        _validate_duplicate(connection_account)
        _reload_access_tokens_by_apps(connection_account)
        integrate_users(connection_account)
        if not lo_types:
            integrate_repositories(connection_account)
            integrate_pull_requests(connection_account)
        integrate_account(connection_account, GITHUB_SYSTEM, N_RECORDS)


def _get_decrypted_installation_field(installation: dict, field: str):
    value = installation.get(field)
    try:
        return decrypt_value(str(value))
    except InvalidToken:
        encrypted_value = encrypt_value(str(value))
        installation[field] = encrypted_value
        return decrypt_value(encrypted_value)


def _reload_access_tokens_by_apps(connection_account: ConnectionAccount):
    installation = connection_account.authentication.get('installation')
    if not installation:
        logger.warning('No Github Apps installations found')
        raise ConfigurationError.bad_client_credentials()
    one_minute = 60
    expiration = int(time.time()) + 3600 - one_minute

    installation_id = installation.get('installation_id')
    access_token = get_installation_access_token(installation_id)['token']
    installation['access_token'] = encrypt_value(access_token)
    connection_account.authentication[TOKEN_EXPIRATION] = expiration
    connection_account.save()
    return installation


def validate_user(new_application: str, connection_account: ConnectionAccount):
    try:
        is_personal_account = get_user(new_application, get_jwt_token())
        if is_personal_account.get('account', {}).get('type') == 'User':
            message = f'Application {new_application} is a personal account'
            handle_wizard_errors(
                connection_account,
                message,
                PERSONAL_ACCOUNT_NOT_ALLOWED,
            )
    except ConnectionResult:
        pass  # Exception is expected for valid data


def validate_organization(new_application: str, connection_account: ConnectionAccount):
    try:
        installed_app = get_organization(new_application, get_jwt_token())
        if connection_account.credentials.get('installationId') != installed_app.get(
            'id'
        ):
            raise ConnectionResult()
        return installed_app.get('id')
    except ConnectionResult:
        message = f'Application {new_application} not installed in Github account'
        handle_wizard_errors(
            connection_account,
            message,
            ORGANIZATION_NOT_INSTALLED,
        )


def _get_customer_installed_apps(
    connection_account: ConnectionAccount, new_application: str
) -> dict:
    validate_user(new_application, connection_account)
    installed_app_id = validate_organization(new_application, connection_account)
    return {
        'login': encrypt_value(new_application),
        'installation_id': installed_app_id,
    }


def integrate_pull_requests(connection_account: ConnectionAccount):
    selected_time_range = calculate_date_range()

    installed_app = get_installation(connection_account)
    application_repositories = read_all_repositories(installed_app)
    for repository in application_repositories:
        repo_name = repository.get("name")
        app_name = installed_app.organization

        logger.info(
            logger_extra(
                f'Fetching pull requests for repo {repo_name} in application {app_name}'
            )
        )
        chunk_count = 1
        end_cursor = None
        hast_next_page = True
        while hast_next_page:
            (
                pull_requests,
                pagination_values,
            ) = get_repository_pull_requests_and_next_page(
                installed_app=installed_app,
                repository=repository,
                hast_next_page=hast_next_page,
                end_cursor=end_cursor,
            )
            message = (
                f'Storing #{len(pull_requests)} pull requests '
                f'in chunk #{chunk_count} for '
                f'repository {repo_name} in application {app_name}'
            )
            logger.info(logger_extra(f'{message}'))
            _store_repository_pull_requests(
                connection_account=connection_account,
                current_pull_requests=pull_requests,
            )
            hast_next_page = pagination_values.get('hast_next_page', False)
            end_cursor = pagination_values.get('end_cursor')
            chunk_count += 1
    lookup_field = 'Updated On'
    clean_up_by_criteria(
        connection_account,
        PULL_REQUEST,
        lookup_query={f'data__{lookup_field}__gt': iso_format(selected_time_range)},
    )


def _store_repository_pull_requests(
    connection_account: ConnectionAccount,
    current_pull_requests: List,
):
    updated_object_keys = update_laika_objects(
        connection_account=connection_account,
        mapper=_get_pull_requests_mapper(),
        raw_objects=current_pull_requests,
        cleanup_objects=False,
    )
    return updated_object_keys


def integrate_users(connection_account: ConnectionAccount):
    user_records = _read_all_organization_users(get_installation(connection_account))
    user_mapper = Mapper(
        map_function=map_users_to_laika_object,
        keys=['Id', 'Organization Name'],
        laika_object_spec=USER,
    )
    update_laika_objects(connection_account, user_mapper, user_records)


def integrate_repositories(connection_account: ConnectionAccount):
    repository_records = _read_all_repositories(get_installation(connection_account))
    repository_mapper = Mapper(
        map_function=map_repository_to_laika_object,
        keys=['Organization', 'Name'],
        laika_object_spec=REPOSITORY,
    )
    update_laika_objects(connection_account, repository_mapper, repository_records)


def _read_all_repositories(github_organization: GithubOrganization):
    repositories = read_all_repositories(github_organization)
    organization = github_organization.organization
    logger.info(f'Repositories for organization {organization} retrieved')
    for repository in repositories:
        yield RepositoryRecord(organization, repository)


def _read_all_organization_users(github_organization: GithubOrganization):
    github_org = github_organization.organization

    organization_users = read_all_organization_users(
        github_organization=github_org,
        token=github_organization.fetch_token,
    )
    members_by_teams = read_all_organization_members_by_teams(
        github_organization=github_org,
        access_token=github_organization.fetch_token,
    )
    team_members: List[Tuple] = []
    for members_by_team in members_by_teams:
        team_members.append(
            TeamMembers(
                team=members_by_team.get('name'),
                members=[
                    user.get('login')
                    for user in members_by_team.get('members', {}).get('nodes', [])
                ],
            )
        )

    for user in organization_users:
        user_data = user['node']
        yield GithubUser(
            id=user_data.get('id'),
            name=user_data.get('name'),
            role=user.get('role'),
            email=user_data.get('email'),
            title=user_data.get('login'),
            has_2fa=user.get('hasTwoFactorEnabled', False),
            organization_name=user_data.get('organization', {}).get('name'),
            teams=[
                team[0]
                for team in list(
                    filter(
                        lambda members: user_data.get('login') in members[1],
                        team_members,
                    )
                )
            ],
        )


def _validate_duplicate(connection_account: ConnectionAccount):
    migrate_old_format(connection_account)
    current_organization = connection_account.credentials.get('organization')
    github_connection_accounts: list[
        ConnectionAccount
    ] = ConnectionAccount.objects.filter(
        organization=connection_account.organization,
        integration=connection_account.integration,
    ).exclude(
        id=connection_account.id
    )

    for github_connection_account in github_connection_accounts:
        organization = github_connection_account.credentials.get('organization')
        if current_organization == organization:
            raise ConnectionAlreadyExists()


def handle_wizard_errors(
    connection_account: ConnectionAccount,
    message: str,
    error_code: str,
) -> None:
    logger.warning(logger_extra(message))
    raise wizard_error(connection_account, error_code)


def adapt_installation(connection, installation):
    connection.authentication['installation'] = installation
    connection.configuration_state['credentials'] = {
        'organization': installation['login']
    }
    if 'installations' in connection.authentication:
        del connection.authentication['installations']
    if 'organizations' in connection.authentication:
        del connection.configuration_state['organizations']
    connection.save()


def migrate_old_format(connection: ConnectionAccount):
    installations = deepcopy(connection.authentication.get('installations', []))
    if not installations:
        return
    installation, *new_installations = installations
    adapt_installation(connection, installation)

    for installation in new_installations:
        ca = clone(connection)
        ca.alias = ca.alias + f'_{installation["login"]}'
        adapt_installation(ca, installation)
        ca.save()
        run(ca)


def clone(instance):
    obj_clone = deepcopy(instance)
    obj_clone.pk = None
    obj_clone.save()
    return obj_clone

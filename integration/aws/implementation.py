import datetime  # noqa
import logging
from collections import namedtuple
from typing import Generator

import boto3
from dateutil.tz import tzlocal  # noqa

from integration.account import get_integration_laika_objects, integrate_account
from integration.store import Mapper, update_laika_objects
from objects.system_types import USER

from ..exceptions import ConnectionAlreadyExists
from ..models import ConnectionAccount
from .aws_client import (
    assume_role_credentials,
    create_external_iam_client,
    create_external_organization_client,
    get_external_role_arn,
    get_organization,
    get_roles_policies,
    get_root_account,
    get_users,
    get_users_groups,
    is_token_expired,
    user_has_mfa,
    user_is_admin,
)
from .constants import ARN_INVALID
from .mapper import map_root_account_to_laika_object, map_user_to_laika_object

logger = logging.getLogger(__name__)

AWS = 'Amazon Web Services (AWS)'
AWSUser = namedtuple('AWSUser', ('user', 'organization', 'is_admin', 'groups', 'mfa'))
AWSRootAccount = namedtuple('AWSRootAccount', ('root_account', 'roles', 'organization'))
N_RECORDS = get_integration_laika_objects(AWS)


def _map_user_groups(external_iam_client: boto3.client, user_name: str) -> str:
    return ', '.join(
        [
            g['GroupName']
            for g in get_users_groups(external_iam_client, user_name)['Groups']
        ]
    )


def run(connection_account: ConnectionAccount) -> None:
    with connection_account.connection_attempt():
        raise_if_duplicate(connection_account)
        if (
            'access_key_id' not in connection_account.authentication
            or is_token_expired(connection_account)
        ):
            connect(connection_account)

        external_iam_client = create_external_iam_client(connection_account)
        external_organization_client = create_external_organization_client(
            connection_account
        )
        organization = get_organization(
            external_organization_client, connection_account
        )
        integrate_users(connection_account, external_iam_client, organization)
        if 'Id' in organization.keys():
            root_account, owner_id = _retrieve_root_account(
                connection_account, external_organization_client
            )
            if root_account:
                integrate_root_account(
                    connection_account, external_iam_client, root_account, organization
                )
        integrate_account(connection_account, AWS, N_RECORDS)


def connect(connection_account: ConnectionAccount) -> None:
    with connection_account.connection_error(error_code=ARN_INVALID):
        if 'credentials' in connection_account.configuration_state:
            assume_role_credentials(connection_account)


def get_aws_users(
    external_iam_client: boto3.client,
    organization: dict,
    connection_account: ConnectionAccount,
) -> Generator:
    organization_name = connection_account.organization.name
    for user in get_users(external_iam_client):
        organization['name'] = organization_name
        username = user['UserName']
        mfa = user_has_mfa(external_iam_client, username)
        is_admin = user_is_admin(external_iam_client, username)
        groups = _map_user_groups(external_iam_client, username)

        user['CreateDate'] = user['CreateDate'].strftime('%h %Y/%m/%d %H:%M')
        if 'PasswordLastUsed' in user:
            user['PasswordLastUsed'] = user['PasswordLastUsed'].strftime(
                '%h %Y/%m/%d %H:%M'
            )
        yield AWSUser(
            user=user,
            organization=organization,
            is_admin=is_admin,
            groups=groups,
            mfa=mfa,
        )


def integrate_users(
    connection_account: ConnectionAccount,
    external_iam_client: boto3.client,
    organization: dict,
) -> None:
    user_mapper = Mapper(
        map_function=map_user_to_laika_object, keys=['Id'], laika_object_spec=USER
    )
    users = get_aws_users(external_iam_client, organization, connection_account)
    update_laika_objects(connection_account, user_mapper, users)


def integrate_root_account(
    connection_account: ConnectionAccount,
    iam_client: boto3.client,
    service_account: dict,
    organization: dict,
) -> None:
    organization['name'] = connection_account.organization.name
    root_account = _generate_root_account(service_account, iam_client, organization)
    service_account_mapper = Mapper(
        map_function=map_root_account_to_laika_object,
        keys=['Id'],
        laika_object_spec=USER,
    )
    update_laika_objects(
        connection_account,
        service_account_mapper,
        [root_account],
        cleanup_objects=False,
    )


def _retrieve_root_account(
    connection_account: ConnectionAccount, organization_client: boto3.client
) -> tuple:
    # Example: arn:aws:iam::123456789244:role/test
    account_id = get_external_role_arn(connection_account).split(':')[4]
    owner_id = account_id
    root_account = get_root_account(organization_client, account_id, connection_account)
    return root_account, owner_id


def _generate_root_account(
    root_account: dict, iam_client: boto3.client, organization: dict
) -> AWSRootAccount:
    root_account['JoinedTimestamp'] = root_account['JoinedTimestamp'].strftime(
        '%d/%m/%Y'
    )
    roles, policies = get_roles_policies(iam_client)
    root_account_roles = _build_root_account_roles_json(roles, policies)
    return AWSRootAccount(
        root_account=root_account, roles=root_account_roles, organization=organization
    )


def raise_if_duplicate(connection_account: ConnectionAccount) -> None:
    arn = get_external_role_arn(connection_account)
    exists = (
        ConnectionAccount.objects.actives(
            configuration_state__credentials__external_role_arn=arn,
            organization=connection_account.organization,
        )
        .exclude(id=connection_account.id)
        .exists()
    )
    if exists:
        raise ConnectionAlreadyExists()


def _build_root_account_roles_json(roles: list[dict], policies: list[dict]) -> dict:
    root_account_roles: dict = {'Roles': []}
    for aws_role in roles:
        role = {
            'RoleName': aws_role.get('RoleName', ''),
            'Policies': {
                policy.get('PolicyName'): get_actions(
                    policies, policy.get('PolicyName')
                )  # noqa
                for policy in aws_role.get('AttachedManagedPolicies', [])
            },
        }
        root_account_roles['Roles'].append(role)
    return root_account_roles


def get_actions(policies: list[dict], policy_name: str) -> list:
    actions: list = list()
    policy = next(
        filter(lambda policy: policy.get('PolicyName') == policy_name, policies)
    )
    for policy_version in policy.get('PolicyVersionList', []):
        policy_statement = policy_version.get('Document', {}).get('Statement', [])
        if isinstance(policy_statement, list):
            actions = map_aws_actions(policy_statement, actions)
        else:
            actions += (
                policy_statement.get('Action')
                if isinstance(policy_statement.get('Action'), list)
                else [policy_statement.get('Action')]
            )
    return list(set(actions))


def map_aws_actions(policy_statement: list, actions: list) -> list:
    for statement in policy_statement:
        aws_actions = statement.get('Action')
        if aws_actions:
            actions += (
                [action for action in aws_actions]
                if isinstance(aws_actions, list)
                else [aws_actions]
            )
    return actions

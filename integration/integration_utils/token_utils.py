from typing import Callable

from integration.asana.rest_client import (
    create_access_token as asana_create_access_token,
)
from integration.azure_boards.rest_client import (
    create_access_token as azure_boards_create_access_token,
)
from integration.azure_devops.rest_client import (
    create_access_token as azure_devops_create_access_token,
)
from integration.intune.rest_client import (
    create_access_token as intune_create_access_token,
)
from integration.jira.rest_client import create_access_token as jira_create_access_token
from integration.microsoft.rest_client import (
    create_access_token as microsoft_365_create_access_token,
)
from integration.models import ConnectionAccount
from integration.token import (
    TokenProvider,
    build_get_access_token,
    build_token_provider,
)
from integration.utils import normalize_integration_name


def get_access_token_callable(vendor_name: str) -> Callable[[str], tuple[str, str]]:
    create_access_token_object = {
        'asana': asana_create_access_token,
        'jira': jira_create_access_token,
        'microsoft_365': microsoft_365_create_access_token,
        'azure_devops': azure_devops_create_access_token,
        'azure_boards': azure_boards_create_access_token,
        'microsoft_intune': intune_create_access_token,
    }
    return create_access_token_object.get(vendor_name, lambda *args: False)


def get_access_token(connection_account: ConnectionAccount) -> str:
    accessor = build_get_access_token(
        get_access_token_callable(_get_vendor_name(connection_account))
    )
    return accessor(connection_account)


def build_fetch_token(connection_account: ConnectionAccount) -> TokenProvider:
    return build_token_provider(
        connection_account,
        get_access_token_callable(_get_vendor_name(connection_account)),
    )


def _get_vendor_name(connection_account: ConnectionAccount) -> str:
    vendor_name = connection_account.integration.vendor.name
    return normalize_integration_name(vendor_name)

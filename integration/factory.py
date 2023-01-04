import integration.asana
import integration.auth0
import integration.aws
import integration.azure
import integration.azure_boards
import integration.azure_devops
import integration.bitbucket
import integration.checkr
import integration.datadog
import integration.digitalocean
import integration.finch
import integration.gcp
import integration.github
import integration.github_apps
import integration.gitlab
import integration.google
import integration.heroku
import integration.intune
import integration.jamf
import integration.jira
import integration.jumpcloud
import integration.linear
import integration.microsoft
import integration.okta
import integration.rippling
import integration.sentry
import integration.shortcut
import integration.slack
import integration.vetty
from integration.constants import AWS_VENDOR, AZURE_VENDOR, GCP_VENDOR, GITHUB_APPS
from integration.log_utils import connection_log
from integration.models import ConnectionAccount
from integration.utils import normalize_integration_name


def get_integration(connection_account: ConnectionAccount):
    vendor_name = connection_account.integration.vendor.name
    if connection_account.integration.metadata.get('finchProvider'):
        return enhance_logs(connection_account, integration.finch)
    return enhance_logs(
        connection_account, integrations().get(normalize_integration_name(vendor_name))
    )


def integrations():
    return {
        'asana': integration.asana,
        normalize_integration_name(AWS_VENDOR): integration.aws,
        normalize_integration_name(AZURE_VENDOR): integration.azure,
        'bitbucket': integration.bitbucket,
        'shortcut': integration.shortcut,
        'datadog': integration.datadog,
        normalize_integration_name(GCP_VENDOR): integration.gcp,
        'github': integration.github,
        'gitlab': integration.gitlab,
        'google_workspace': integration.google,
        'heroku': integration.heroku,
        'jamf': integration.jamf,
        'jira': integration.jira,
        'linear': integration.linear,
        'microsoft_365': integration.microsoft,
        'okta': integration.okta,
        'rippling': integration.rippling,
        'sentry': integration.sentry,
        'vetty': integration.vetty,
        normalize_integration_name(GITHUB_APPS): integration.github_apps,
        'slack': integration.slack,
        'checkr': integration.checkr,
        'jumpcloud': integration.jumpcloud,
        normalize_integration_name('Azure DevOps'): integration.azure_devops,
        normalize_integration_name('Azure Boards'): integration.azure_boards,
        normalize_integration_name('Microsoft Intune'): integration.intune,
        'digitalocean': integration.digitalocean,
        'auth0': integration.auth0,
    }


def get_integration_name(key: str):
    names = {
        normalize_integration_name(AWS_VENDOR): AWS_VENDOR,
        normalize_integration_name(AZURE_VENDOR): AZURE_VENDOR,
        normalize_integration_name(GCP_VENDOR): GCP_VENDOR,
        normalize_integration_name(GITHUB_APPS): GITHUB_APPS,
    }
    return names[key] if key in names else key.replace('_', ' ').title()


def enhance_logs(connection, integration_module):
    """
    This function wraps an integration module and intercepts callables to be
    executed using context manager connection_log. This allows logger
    functions access to ConnectionAccount object from ContextVar to avoid
    excessive argument propagation.
    """
    if integration_module is None:
        return None
    return EnhanceLogWrapper(connection, integration_module)


class EnhanceLogWrapper:
    def __init__(self, connection, integration_module):
        self.connection = connection
        self.integration_module = integration_module

    def __getattr__(self, attr):
        member = getattr(self.integration_module, attr)
        if hasattr(member, '__call__'):
            return self._enhance_log(member)
        return member

    def _enhance_log(self, call):
        def log(*args, **kwargs):
            with connection_log(self.connection):
                return call(*args, **kwargs)

        return log

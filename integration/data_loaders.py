from promise import Promise

from laika.data_loaders import ContextDataLoader

from .models import ConnectionAccount, ErrorCatalogue


class IntegrationLoaders:
    def __init__(self, context):
        self.connection_accounts_by_org = ConnectionAccountLoader.with_context(context)
        self.connection_account_error = ErrorCatalogueLoader.with_context(context)


class ConnectionAccountLoader(ContextDataLoader):
    def batch_load_fn(self, keys):
        connections_dictionary = {}
        for connection in ConnectionAccount.objects.filter(
            integration_id__in=keys, organization=self.context.user.organization
        ):
            connections_dictionary.setdefault(connection.integration.id, []).append(
                connection
            )
        return Promise.resolve(
            [connections_dictionary.get(integration_id, []) for integration_id in keys]
        )


class ErrorCatalogueLoader(ContextDataLoader):
    @staticmethod
    def batch_load_fn(keys):
        errors_dictionary = {}
        for error in ErrorCatalogue.objects.filter(
            code__in=keys,
        ):
            errors_dictionary[error.code] = error.failure_reason_mail
        return Promise.resolve(
            [errors_dictionary.get(error_code, '') for error_code in keys]
        )

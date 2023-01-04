from django.utils.module_loading import import_string

from integration.checkr.constants import CHECKR_ENDPOINTS
from integration.execute_api.execute_api import ExecuteAPIInterface
from integration.models import ConnectionAccount
from laika.utils.exceptions import ServiceException


class ExecuteCheckerAPI(ExecuteAPIInterface):
    def execute(self, endpoint: str, connection_account: ConnectionAccount, **kwargs):
        endpoint_data = CHECKR_ENDPOINTS.get(endpoint)
        if endpoint_data is None or endpoint_data.get('method') is None:
            raise ServiceException('The endpoint is not valid')
        auth_token = connection_account.authentication.get('access_token')
        if auth_token is None:
            return ServiceException('The connection account does not have token')
        rest_client_file = import_string('integration.checkr.rest_client')
        method = getattr(rest_client_file, endpoint_data['method'], None)

        if method is None:
            return ServiceException('The method is invalid')

        merged_kwargs = {**dict(connection_account=connection_account), **kwargs}

        return method(
            auth_token=auth_token, url=endpoint_data.get('url'), **merged_kwargs
        )

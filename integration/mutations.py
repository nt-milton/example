import logging
import timeit
import uuid
from typing import Dict

import graphene
import reversion

from laika.decorators import laika_service
from laika.utils.exceptions import ServiceException, format_stack_in_one_line
from vendor.models import OrganizationVendor, Vendor

from . import factory
from .constants import DELETING, ERROR, PENDING, SETUP_COMPLETE
from .error_codes import NONE, OTHER, USER_INPUT_ERROR
from .exceptions import ConfigurationError, ConnectionAccountSyncing
from .execute_api.constants import VENDOR_EXECUTION_API
from .models import SYNC, ConnectionAccount, Integration
from .types import ConnectionResponseType, ConnectionSetupError
from .utils import get_oldest_connection_account_by_vendor_name, join_reversion_messages

logger = logging.getLogger(__name__)


class StartIntegration(graphene.Mutation):
    connection_account = graphene.Field(ConnectionResponseType)

    class Arguments:
        vendor_name = graphene.String()
        alias = graphene.String()
        subscription_type = graphene.String()

    @laika_service(
        permission='integration.add_connectionaccount',
        exception_msg='Failed to start integration',
        revision_name='Connection account created.',
    )
    def mutate(self, info, vendor_name, alias, subscription_type):
        vendor = Vendor.objects.get(name=vendor_name)
        organization = info.context.user.organization
        organization_vendor, _ = OrganizationVendor.objects.get_or_create(
            vendor=vendor, organization=organization
        )
        integration = Integration.objects.get(vendor=vendor)
        ConnectionAccount.objects.validate_duplicated_alias(
            organization, integration, alias
        )
        init_configuration_state: Dict = (
            dict(subscriptionType=subscription_type)
            if len(subscription_type) > 0
            else {}
        )
        connection_account = ConnectionAccount.objects.create(
            organization=organization,
            integration=integration,
            authentication={},
            alias=alias,
            created_by=info.context.user,
            configuration_state=init_configuration_state,
            control=uuid.uuid4(),
            integration_version=integration.get_latest_version(),
        )
        logger.info(f'Connection account {connection_account.id} created.')
        return StartIntegration(connection_account=connection_account)


class DeleteConnectionAccount(graphene.Mutation):
    connection_account = graphene.Field(ConnectionResponseType)

    class Arguments:
        id = graphene.Int()

    @laika_service(
        permission='integration.delete_connectionaccount',
        exception_msg='Failed to delete connection account',
    )
    def mutate(self, info, id):
        connection_account = ConnectionAccount.objects.get(
            id=id, organization=info.context.user.organization
        )
        if connection_account and connection_account.status != SYNC:
            connection_account.status = DELETING
            connection_account.save()
            with reversion.create_revision():
                cleanup_connection(connection_account)
                reversion.set_user(info.context.user)
                reversion.set_comment('Connection account deleted.')
                logger.info(f'Connection account {connection_account.id} deleted.')
                connection_account.delete()
        else:
            raise ConnectionAccountSyncing(
                'Cannot delete as connection account is syncing'
            )
        return DeleteConnectionAccount(connection_account=connection_account)


class UpdateConnectionAccount(graphene.Mutation):
    connection_account = graphene.Field(ConnectionResponseType)
    connection_setup_error = graphene.Field(ConnectionSetupError)

    class Arguments:
        id = graphene.Int()
        alias = graphene.String()
        configuration_state = graphene.JSONString()
        completed = graphene.Boolean()

    @laika_service(
        permission='integration.change_connectionaccount',
        exception_msg='Failed to update connection account',
    )
    def mutate(self, info, id, configuration_state=None, alias=None, completed=None):
        start_time = timeit.default_timer()
        wizard_message = None
        connection_setup_error = ConnectionSetupError()
        connection_account = ConnectionAccount.objects.get(
            id=id, organization=info.context.user.organization
        )
        try:
            if alias:
                connection_account.alias = alias
                connection_account.bulk_update_objects_connection_name(new_alias=alias)

            if configuration_state:
                update_configuration_state(configuration_state, connection_account)
            if completed:
                connection_account.integration_version = (
                    connection_account.integration.get_latest_version()
                )
                if connection_account.status == PENDING:
                    # Triggers the signal and start running the integration
                    connection_account.status = SETUP_COMPLETE

            connection_account.save()
            logger.info(f'Connection account {connection_account.id} updated.')
        except ConfigurationError as ce:
            if ce.is_user_input_error:
                wizard_message = f'user input error => {ce.error_message}'
                connection_setup_error = ConnectionSetupError(
                    is_user_input_error=True, setup_error_message=ce.error_message
                )
        finally:
            with reversion.create_revision():
                reversion.set_user(info.context.user)
                comment = f'Updated status to => {connection_account.status}'
                reversion.set_comment(
                    join_reversion_messages([comment, wizard_message])
                )
        execution_time = timeit.default_timer() - start_time
        logger.info(f'Updating connection account took: {execution_time}')
        return UpdateConnectionAccount(
            connection_account=connection_account,
            connection_setup_error=connection_setup_error,
        )


class ExecuteIntegrationAPI(graphene.Mutation):
    response = graphene.JSONString()

    class Arguments:
        endpoint = graphene.String(required=True)
        vendor = graphene.String(required=True)
        data = graphene.JSONString()
        params = graphene.JSONString()

    @laika_service(
        permission='integration.view_integration',
        exception_msg='Failed to make operations in the API',
    )
    def mutate(self, info, **kwargs):
        endpoint = kwargs.pop('endpoint', None)
        vendor = kwargs.pop('vendor', None)
        organization = info.context.user.organization
        connection_account = get_oldest_connection_account_by_vendor_name(
            organization, vendor
        )
        if connection_account is None:
            logger.error(
                'Connection account for this vendor and organization'
                f' {organization.id} {vendor} does not exist.'
            )
            return None

        class_handler = VENDOR_EXECUTION_API.get(vendor)
        if class_handler:
            api = class_handler()
            data = api.execute(endpoint, connection_account, **kwargs)
        else:
            logger.error(f'The vendor - {vendor} has not implemented execution class')
            raise ServiceException(f'The handler for this vendor {vendor} is undefined')

        return ExecuteIntegrationAPI(response=data)


def update_configuration_state(
    new_configuration_state: Dict, connection_account: ConnectionAccount
) -> None:
    new = new_configuration_state.get('credentials')
    old = connection_account.configuration_state.get('credentials')
    connection_account.configuration_state = new_configuration_state
    is_user_input_error = connection_account.error_code == USER_INPUT_ERROR
    if new != old or is_user_input_error:
        connect(connection_account)


def connect(connection_account: ConnectionAccount):
    try:
        integration = factory.get_integration(connection_account)
        integration.connect(connection_account)
        connection_account.status = PENDING
        connection_account.error_code = NONE
    except ConfigurationError as err:
        logger.exception(
            f'Connection account {connection_account.id} - '
            f'Configuration error: {format_stack_in_one_line(err)}'
        )
        if err.is_user_input_error:
            connection_account.result.update(
                dict(error_response=str(err.error_response))
            )
            connection_account.save()
            raise
        connection_account.status = ERROR
        connection_account.error_code = err.error_code
    except Exception as exc:
        logger.exception(
            f'Connection account {connection_account.id} - '
            f'Error: {format_stack_in_one_line(exc)}'
        )
        connection_account.status = ERROR
        connection_account.error_code = OTHER


def cleanup_connection(connection_account: ConnectionAccount):
    configuration_state = connection_account.configuration_state
    settings = configuration_state.get('settings', {})
    template_state = settings.get('templateState', {})
    template_key = template_state.get('templateKey')
    if not template_key:
        return
    try:
        integration = factory.get_integration(connection_account)
        integration.cleanup_connection(template_key)
    except ConfigurationError as err:
        connection_account.status = ERROR
        connection_account.error_code = err.error_code

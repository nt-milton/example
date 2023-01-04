import graphene

from integration.mutations import (
    DeleteConnectionAccount,
    ExecuteIntegrationAPI,
    StartIntegration,
    UpdateConnectionAccount,
)
from laika.decorators import laika_service
from objects.models import LaikaObject

from .exceptions import ConnectionResult
from .factory import get_integration
from .models import ConnectionAccount, Integration
from .types import (
    ConnectionResponseType,
    FieldOptionsResponseType,
    GoogleCloudServicesType,
    GoogleOrganizationsType,
    IntegrationResponseType,
    SlackChannelsType,
)
from .utils import PREFETCH, get_oldest_connection_account_by_vendor_name


class Mutation(graphene.ObjectType):
    start_integration = StartIntegration.Field()
    delete_connection_account = DeleteConnectionAccount.Field()
    update_connection_account = UpdateConnectionAccount.Field()
    execute_integration_api = ExecuteIntegrationAPI.Field()


class Query(object):
    integrations = graphene.List(IntegrationResponseType)
    integration = graphene.Field(IntegrationResponseType, name=graphene.String())
    connection_account = graphene.Field(
        ConnectionResponseType, control=graphene.String(), vendor_name=graphene.String()
    )
    object_connection_account = graphene.Field(
        ConnectionResponseType,
        object_type_name=graphene.String(required=True),
        object_id=graphene.Int(required=True),
    )
    get_custom_field_options = graphene.Field(
        FieldOptionsResponseType,
        connection_id=graphene.Int(),
        field_name=graphene.String(),
    )
    get_google_cloud_services = graphene.Field(
        GoogleCloudServicesType,
        connection_id=graphene.Int(),
    )
    get_slack_channels = graphene.Field(
        SlackChannelsType,
        connection_id=graphene.Int(),
    )
    get_google_organizations = graphene.Field(
        GoogleOrganizationsType,
        connection_id=graphene.Int(),
    )

    @laika_service(
        permission='integration.view_integration',
        exception_msg='Failed to list integrations',
    )
    def resolve_integrations(self, info, **kwargs):
        return Integration.objects.actives()

    @laika_service(
        permission='integration.view_integration',
        exception_msg='Failed to retrieve integration',
    )
    def resolve_integration(self, info, name):
        return Integration.objects.actives().get(vendor__name=name)

    @laika_service(
        permission='integration.add_connectionaccount',
        exception_msg='Failed to create connection account',
    )
    def resolve_connection_account(self, info, **kwargs):
        control = kwargs.get('control')
        vendor_name = kwargs.get('vendor_name')
        organization = info.context.user.organization
        if control:
            return ConnectionAccount.objects.get(
                control=control, organization=organization
            )
        elif vendor_name:
            return get_oldest_connection_account_by_vendor_name(
                organization, vendor_name
            )

    @laika_service(
        atomic=False,
        permission='objects.view_laikaobject',
        exception_msg='Failed to retrieve connection account',
    )
    def resolve_object_connection_account(self, info, **kwargs):
        object_id = kwargs.get('object_id')
        object_type_name = kwargs.get('object_type_name')

        if object_id and object_type_name:
            laika_object = LaikaObject.objects.filter(
                id=object_id,
                object_type__organization=info.context.user.organization,
                object_type__type_name=object_type_name,
            ).first()

            if laika_object is not None:
                return laika_object.connection_account
            return None

    @laika_service(
        permission='integration.view_connectionaccount',
        exception_msg='Failed to retrieve connection account',
    )
    def resolve_get_custom_field_options(self, info, connection_id, field_name):
        connection_account = ConnectionAccount.objects.get(
            id=connection_id, organization=info.context.user.organization
        )
        custom_fields = connection_account.integration.metadata['configuration_fields']
        if field_name not in custom_fields:
            raise ValueError(f'Field {field_name} does not exist')

        integration = get_integration(connection_account)
        if connection_account.authentication.get(f'{PREFETCH}{field_name}'):
            return FieldOptionsResponseType(
                options=connection_account.authentication.get(f'{PREFETCH}{field_name}')
            )

        try:
            return integration.get_custom_field_options(field_name, connection_account)
        except ConnectionResult as cr_exc:
            connection_account.result = cr_exc.error_response
            connection_account.save()
            return Exception('Error getting configuration options')

    @laika_service(
        permission='integration.view_connectionaccount',
        exception_msg='Failed to retrieve google cloud services',
    )
    def resolve_get_google_cloud_services(self, info, connection_id):
        connection_account = ConnectionAccount.objects.get(
            id=connection_id, organization=info.context.user.organization
        )
        integration = get_integration(connection_account)
        return integration.get_services(connection_account)

    @laika_service(
        permission='integration.view_connectionaccount',
        exception_msg='Failed to retrieve slack channels',
    )
    def resolve_get_slack_channels(self, info, connection_id):
        connection_account = ConnectionAccount.objects.get(
            id=connection_id, organization=info.context.user.organization
        )
        integration = get_integration(connection_account)
        return integration.get_slack_channels(connection_account)

    @laika_service(
        permission='integration.view_connectionaccount',
        exception_msg='Failed to retrieve google organizations',
    )
    def resolve_get_google_organizations(self, info, connection_id):
        connection_account = ConnectionAccount.objects.get(
            id=connection_id, organization=info.context.user.organization
        )
        integration = get_integration(connection_account)
        return integration.get_google_organizations(connection_account)

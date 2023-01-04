import graphene

from access_review.utils import check_if_vendor_is_used_by_ongoing_ac
from integration.constants import PUBLIC_AUTHENTICATION_KEYS
from integration.models import ConnectionAccount, Integration
from integration.utils import _get_wizard_error_message
from user.types import UserType
from vendor.schema import VendorType


class ConnectionAccountDebugActionType(graphene.ObjectType):
    name = graphene.String()
    status = graphene.String()
    description = graphene.String()
    created_at = graphene.DateTime()
    updated_at = graphene.DateTime()


class ConnectionResponseType(graphene.ObjectType):
    class Meta:
        model = ConnectionAccount

    id = graphene.ID()
    created_at = graphene.DateTime()
    updated_at = graphene.DateTime()
    alias = graphene.String()
    control = graphene.String()
    status = graphene.String()
    error_code = graphene.String()
    created_by = graphene.Field(UserType)
    configuration_state = graphene.JSONString()

    integration = graphene.Field(lambda: IntegrationResponseType)
    error_message = graphene.String()
    authentication_metadata = graphene.JSONString()
    permissions = graphene.JSONString()
    error_code_message = graphene.String()
    debug_status = graphene.Field(ConnectionAccountDebugActionType)

    def resolve_integration(self, info):
        if self.integration:
            return self.integration

    def resolve_error_message(self, info):
        error = self.get_error_in_catalogue()

        if not error:
            return ''

        error_message = _get_wizard_error_message(self, error)
        return error_message

    def resolve_authentication_metadata(self, info):
        authentication_fields = PUBLIC_AUTHENTICATION_KEYS.get(
            self.integration.vendor.name.lower(), {}
        )
        return {item: self.authentication.get(item) for item in authentication_fields}

    def resolve_permissions(self, info):
        return self.integration_version.metadata.get('permissions', {})

    @staticmethod
    def resolve_created_by(root, info):
        user_loader = info.context.loaders.user
        return user_loader.users_by_id.load(root.created_by_id)

    def resolve_error_code_message(self, info):
        ca_loader = info.context.loaders.integration
        return ca_loader.connection_account_error.load(self.error_code)


class MetadataResponseType(graphene.ObjectType):
    key = graphene.String()
    value = graphene.String()


class IntegrationResponseType(graphene.ObjectType):
    class Meta:
        model = Integration

    id = graphene.ID()
    vendor = graphene.Field(VendorType)
    description = graphene.String()
    category = graphene.String()
    metadata = graphene.List(MetadataResponseType)
    requirements = graphene.List(graphene.String)
    connection_accounts = graphene.List(lambda: ConnectionResponseType)
    permissions = graphene.JSONString()
    is_ac_in_progress = graphene.Boolean()

    def resolve_metadata(self, info):
        if not self.metadata:
            return None
        return [MetadataResponseType(key=k, value=v) for k, v in self.metadata.items()]

    def resolve_requirements(self, info):
        return self.get_requirements()

    def resolve_permissions(self, info):
        latest_version = self.get_latest_version()
        if latest_version:
            return latest_version.metadata.get('permissions', {})
        return {}

    @staticmethod
    def resolve_vendor(root, info):
        vendor_loader = info.context.loaders.vendor
        return vendor_loader.vendors_by_id.load(root.vendor_id)

    @staticmethod
    def resolve_connection_accounts(root, info):
        ca_loader = info.context.loaders.integration
        return ca_loader.connection_accounts_by_org.load(root.id)

    def resolve_is_ac_in_progress(self, info):
        return check_if_vendor_is_used_by_ongoing_ac(
            vendor=self.vendor, organization=info.context.user.organization
        )


class OptionType(graphene.ObjectType):
    id = graphene.String()
    value = graphene.JSONString()


class FieldOptionsResponseType(graphene.ObjectType):
    total = graphene.Int()
    options = graphene.List(OptionType)

    def resolve_total(self, info):
        return len(self.options)


class GoogleErrorType(graphene.ObjectType):
    code = graphene.String()
    message = graphene.String()


class GoogleOrganizationsType(graphene.ObjectType):
    error = graphene.Field(GoogleErrorType)
    options = graphene.List(OptionType)


class GoogleCloudServiceType(graphene.ObjectType):
    title = graphene.String()
    name = graphene.String()
    state = graphene.String()


class GoogleCloudServicesType(graphene.ObjectType):
    services = graphene.List(GoogleCloudServiceType)


class SlackChannelType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    is_im = graphene.Boolean()
    is_group = graphene.Boolean()
    is_channel = graphene.Boolean()
    is_private = graphene.Boolean()


class SlackChannelsType(graphene.ObjectType):
    channels = graphene.List(SlackChannelType)


# Error on Wizard connection setup
class ConnectionSetupError(graphene.ObjectType):
    is_user_input_error = graphene.Boolean(default_value=False)
    setup_error_message = graphene.String(default_value='')

import graphene

from address.models import Address
from address.schema import AddressInput
from laika import types
from user.inputs import UserInput

from .models import Onboarding


class UpdateOnboardingInput(types.DjangoInputObjectBaseType):
    state = graphene.String(required=True)

    class InputMeta:
        model = Onboarding


class LocationInput(graphene.InputObjectType):
    street1 = graphene.String()
    street2 = graphene.String()
    city = graphene.String()
    country = graphene.String()
    state = graphene.String()
    zip_code = graphene.String()
    unit = graphene.String()
    name = graphene.String()
    hq = graphene.Boolean()


class UpdateLocationInput(LocationInput, types.DjangoInputObjectBaseType):
    id = graphene.Int(required=True)

    class InputMeta:
        model = Address


class OrganizationFilterType(graphene.InputObjectType):
    field = graphene.String(required=True)
    value = graphene.String()
    operator = graphene.String(required=True)
    type = graphene.String(required=True)


class OrganizationCheckInFilterType(OrganizationFilterType):
    pass


class OrganizationInput(graphene.InputObjectType):
    name = graphene.String()
    description = graphene.String()
    tier = graphene.String()
    billing_address = graphene.Field(AddressInput)
    website = graphene.String()
    is_public_company = graphene.Boolean()
    number_of_employees = graphene.Int()
    business_inception_date = graphene.Date()
    contract_sign_date = graphene.Date()
    target_audit_date = graphene.Date()
    product_or_service_description = graphene.String()
    file_name = graphene.String()
    file_contents = graphene.String()
    legal_name = graphene.String()
    state = graphene.String()
    customer_success_manager = graphene.Field(UserInput)
    compliance_architect = graphene.Field(UserInput)
    sfdc_id = graphene.String()
    is_internal = graphene.Boolean()
    calendly_url = graphene.String()


class OrganizationByIdInput(OrganizationInput):
    id = graphene.String(required=True)
    billing_address = graphene.String()
    customer_success_manager_user = graphene.Field(UserInput)
    compliance_architect_user = graphene.Field(UserInput)
    file_name = graphene.String()
    file_contents = graphene.String()
    business_inception_date = graphene.Date()
    target_audit_date = graphene.Date()


class OnboardingStepCompletionInput(graphene.InputObjectType):
    organization_id = graphene.String(required=True)
    name = graphene.String(required=True)
    completed = graphene.Boolean(required=True)


class MoveOrgOutOfOnboardingInput(graphene.InputObjectType):
    organization_id = graphene.String(required=True)


class CreateOrganizationCheckInInput(graphene.InputObjectType):
    id = graphene.UUID(required=True)
    date = graphene.Date(required=True)
    cx_id = graphene.String(required=True)
    customer_participant = graphene.String()
    notes = graphene.String(required=True)
    action_items = graphene.String(required=True)


class DeleteOrganizationCheckInInput(graphene.InputObjectType):
    check_in_ids = graphene.List(graphene.String, required=True)


class MigrateOrganizationPayload(graphene.InputObjectType):
    id = graphene.String(required=True)
    frameworks = graphene.List(graphene.String, required=True)
    assignee = graphene.String(required=True)


class RoadmapFilterInputType(graphene.InputObjectType):
    framework = graphene.String()

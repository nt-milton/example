import datetime

import graphene
from graphene_django.types import DjangoObjectType

from address.schema import AddressType
from control.roadmap.types import ControlGroupType
from control.types import ControlType
from dashboard.types import ActionItemTypeV2
from feature.constants import new_controls_feature_flag
from feature.types import FlagType
from laika.settings import DJANGO_SETTINGS
from laika.types import BaseResponseType, FileType, PaginationResponseType
from organization.calendly.rest_client import get_event
from organization.roadmap_helper import (
    get_roadmap_backlog_implemented_controls,
    get_roadmap_backlog_total_controls,
    get_roadmap_groups_implemented_controls,
    get_roadmap_groups_total_controls,
)
from tag.types import TagType
from user.types import OfficerType, TeamType, UserType
from vendor.schema import VendorType

from .models import (
    TIERS,
    ApiTokenHistory,
    CheckIn,
    OffboardingVendor,
    Onboarding,
    OnboardingSetupStep,
    Organization,
    OrganizationChecklist,
    OrganizationChecklistRun,
    OrganizationChecklistRunSteps,
)
from .offboarding.offboarding_content import (
    get_non_integrated_vendors,
    get_offboarding_steps,
    get_offboarding_vendors,
)

ONBOARDING_TYPEFORM_FORM = DJANGO_SETTINGS.get('ONBOARDING_TYPEFORM_FORM')
ONBOARDING_TECH_TYPEFORM_FORM = DJANGO_SETTINGS.get('ONBOARDING_TECH_TYPEFORM_FORM')


class OrganizationType(DjangoObjectType):
    class Meta:
        model = Organization

    tier = graphene.String()
    # These are using legacy object types,
    # will be changed once officers and teams are migrated
    officers = graphene.List(OfficerType)
    teams = graphene.List(TeamType)
    customer_success_manager = graphene.Field(UserType)
    compliance_architect = graphene.Field(UserType)
    is_public_company = graphene.Boolean()
    feature_flags = graphene.List(FlagType)
    content_type = graphene.String()

    def resolve_feature_flags(self, info):
        return self.feature_flags.all()

    def resolve_tier(self, info):
        return [t for t in TIERS if t[0] == self.tier][0][1].upper()

    def resolve_officers(self, info):
        return self.officers.all()

    def resolve_teams(self, info):
        return self.teams.all()

    def resolve_logo(self, info):
        return self.logo.url if self.logo else ''

    def resolve_customer_success_manager(self, info):
        return self.customer_success_manager_user

    def resolve_compliance_architect(self, info):
        return self.compliance_architect_user

    def resolve_is_public_company(self, info):
        return self.is_public_company

    def resolve_content_type(self, info):
        return (
            'My Compliance'
            if self.is_flag_active(new_controls_feature_flag)
            else 'Playbooks'
        )


class SetupStepType(DjangoObjectType):
    class Meta:
        model = OnboardingSetupStep


class CheckInType(DjangoObjectType):
    class Meta:
        model = CheckIn


class OrganizationsResponseType(graphene.ObjectType):
    data = graphene.List(OrganizationType)
    pagination = graphene.Field(PaginationResponseType)


class OrganizationResponseType(BaseResponseType):
    data = graphene.Field(OrganizationType)
    permissions = graphene.List(graphene.String)


class CheckInResponseType(graphene.ObjectType):
    data = graphene.List(CheckInType)
    pagination = graphene.Field(PaginationResponseType)


class OnboardingExpertType(graphene.ObjectType):
    firstName = graphene.String()
    lastName = graphene.String()
    email = graphene.String()


class OrganizationBaseType(DjangoObjectType):
    class Meta:
        model = Organization

    address = graphene.Field(AddressType)

    def resolve_address(self, info):
        return self.billing_address


class OnboardingResponseType(DjangoObjectType):
    class Meta:
        model = Onboarding

    id = graphene.Int()
    organization = graphene.Field(OrganizationBaseType)
    expiration_days = graphene.Int()
    can_go_back = graphene.Boolean()
    setup_steps = graphene.List(SetupStepType)
    state_v2 = graphene.String()
    calendly_url_v2 = graphene.String()
    calendly_invitee_id_v2 = graphene.String()
    architect_meeting_v2 = graphene.String()

    def resolve_organization(self, info):
        return self.organization

    def resolve_expiration_days(self, info):
        today = datetime.date.today()

        time_difference = self.period_ends - today

        return time_difference.days if time_difference.days >= 1 else 0

    def resolve_can_go_back(self, info):
        return self.state in ['INIT', 'ENROLLED']

    def resolve_setup_steps(self, info):
        return self.setup_steps.all()

    def resolve_state_v2(self, info):
        return self.state_v2

    def resolve_calendly_url_v2(self, info):
        return self.organization.calendly_url

    def resolve_architect_meeting_v2(self, info):
        if self.calendly_event_id_v2 is not None:
            calendly_event = get_event(self.calendly_event_id_v2)
            return calendly_event['start_time']
        return None


class LocationResponseType(graphene.ObjectType):
    id = graphene.Int()
    street1 = graphene.String()
    street2 = graphene.String()
    city = graphene.String()
    country = graphene.String()
    state = graphene.String()
    zip_code = graphene.String()
    name = graphene.String()
    hq = graphene.Boolean()


class OrganizationChecklistType(DjangoObjectType):
    class Meta:
        model = OrganizationChecklist

    tags = graphene.List(TagType)
    action_item = graphene.Field(ActionItemTypeV2)

    def resolve_tags(self, info):
        return self.tags.all()


class CheckListStepType(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()
    description = graphene.String()
    metadata = graphene.JSONString()


class OrganizationChecklistRunStepsType(DjangoObjectType):
    class Meta:
        model = OrganizationChecklistRunSteps


class OffboardingVendorType(DjangoObjectType):
    class Meta:
        model = OffboardingVendor
        convert_choices_to_enum = False

    id = graphene.Int(required=False)


class OffboardingStepType(DjangoObjectType):
    class Meta:
        model = OrganizationChecklistRunSteps
        convert_choices_to_enum = False


class OffboardingRunVendorType(graphene.ObjectType):
    def __init__(self, checklist_run_id, vendor, offboarding_state=None):
        self.checklist_run_id = checklist_run_id
        self.vendor = vendor
        self.offboarding_state = offboarding_state

    vendor = graphene.Field(VendorType)
    offboarding_state = graphene.Field(OffboardingVendorType)

    def resolve_offboarding_state(self, info):
        if self.offboarding_state:
            return self.offboarding_state
        try:
            return OffboardingVendor.objects.get(
                checklist_run_id=self.checklist_run_id, vendor=self.vendor
            )
        except OffboardingVendor.DoesNotExist:
            return None


class OffboardingRunStepType(graphene.ObjectType):
    def __init__(self, checklist_run_id, step, offboarding_state):
        self.checklist_run_id = checklist_run_id
        self.step = step
        self.offboarding_state = offboarding_state

    step = graphene.Field(ActionItemTypeV2)
    offboarding_state = graphene.Field(OffboardingStepType)

    def resolve_offboarding_state(self, info):
        return self.offboarding_state or None


class OffboardingRunType(graphene.ObjectType):
    def __init__(self, checklist_run):
        self.checklist_run = checklist_run

    integrated_vendors = graphene.List(OffboardingRunVendorType)
    non_integrated_vendors = graphene.List(OffboardingRunVendorType)
    steps = graphene.List(OffboardingRunStepType)

    def resolve_integrated_vendors(self, info):
        return get_offboarding_vendors(self.checklist_run)

    def resolve_non_integrated_vendors(self, info):
        return get_non_integrated_vendors(self.checklist_run)

    def resolve_steps(self, info):
        return get_offboarding_steps(self.checklist_run)


class OrganizationChecklistRunType(DjangoObjectType):
    class Meta:
        model = OrganizationChecklistRun

    document = graphene.Field(FileType)

    offboarding_run = graphene.Field(OffboardingRunType)

    def resolve_document(self, info):
        return self.document or None

    def resolve_offboarding_run(self, info):
        return OffboardingRunType(checklist_run=self)


class OrganizationChecklistRunResourceType(graphene.ObjectType):
    id = graphene.Int()
    date = graphene.Date()
    status = graphene.String()


class RoadmapType(graphene.ObjectType):
    completion_date = graphene.Date()
    groups = graphene.List(ControlGroupType)
    backlog = graphene.List(ControlType)
    implemented_controls = graphene.Int()
    total_controls = graphene.Int()

    def resolve_implemented_controls(self, info):
        return get_roadmap_groups_implemented_controls(
            self.groups
        ) + get_roadmap_backlog_implemented_controls(self.backlog)

    def resolve_total_controls(self, info):
        return get_roadmap_groups_total_controls(
            self.groups
        ) + get_roadmap_backlog_total_controls(self.backlog)


class ApiTokenHistoryType(DjangoObjectType):
    class Meta:
        model = ApiTokenHistory

    created_by = graphene.Field(UserType)

    @staticmethod
    def resolve_created_by(root, info):
        user_loader = info.context.loaders.user
        return user_loader.users_by_id.load(root.created_by_id)

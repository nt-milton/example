import logging

import graphene
from graphene_django.types import DjangoObjectType

from action_item.constants import TYPE_POLICY
from action_item.models import ActionItem
from dashboard.types import ActionItemTypeV2
from laika.types import BaseResponseType, PaginationResponseType
from laika.utils.permissions import map_permissions
from organization.constants import ACTION_ITEM_OFFBOARDING
from user.helpers import calculate_user_status, get_help_center_hash
from user.models import Officer, Partner, Team, TeamMember, User

logger = logging.getLogger('user')


class PermissionType(graphene.ObjectType):
    id = graphene.Int()
    application_name = graphene.String()
    permissions = graphene.List(graphene.String)


class ProfilePictureType(graphene.ObjectType):
    id = graphene.String()
    url = graphene.String()


class UserType(DjangoObjectType):
    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
            'role',
            'title',
            'manager',
            'department',
            'employment_type',
            'employment_subtype',
            'background_check_status',
            'background_check_passed_on',
            'start_date',
            'end_date',
            'employment_status',
            'phone_number',
            'is_active',
            'discovery_state',
            'compliant_completed',
            'security_training',
            'deleted_at',
            'checklist_runs',
        )

    id = graphene.String()
    last_name = graphene.String()
    permissions = graphene.List(graphene.String)
    all_permissions = graphene.List(PermissionType)
    role = graphene.String()
    organization_id = graphene.UUID()
    last_activity_date = graphene.DateTime()
    status = graphene.String()
    user_preferences = graphene.JSONString()
    title = graphene.String()
    manager = graphene.Field(lambda: UserType)
    department = graphene.String()
    employment_type = graphene.String()
    employment_subtype = graphene.String()
    start_date = graphene.DateTime()
    background_check_status = graphene.String()
    background_check_passed_on = graphene.DateTime()
    end_date = graphene.DateTime()
    employment_status = graphene.String()
    phone_number = graphene.String()
    profile_picture = graphene.Field(ProfilePictureType)
    is_active = graphene.Boolean()
    discovery_state = graphene.String()
    missing_mfa = graphene.Boolean()
    lo_user_ids = graphene.JSONString()
    offboarding = graphene.Field('organization.types.OrganizationChecklistRunType')
    policies_reviewed = graphene.Boolean()
    policies_reviewed_data = graphene.List(ActionItemTypeV2)
    help_center_hash = graphene.String()

    def resolve_lo_user_ids(self, info):
        user_loader = info.context.loaders.user
        return user_loader.lo_user_ids.load(self)

    def resolve_missing_mfa(self, info):
        return info.context.user.is_missing_mfa()

    def resolve_permissions(self, info):
        permissions = map_permissions(info.context.user, 'user', [self])

        return permissions

    def resolve_id(self, info):
        # For partial stored users we need to return the id in the meantime
        # as username has not being set yet so the FE
        # can differentiate the users when rendering (controls, policies...)
        return self.username if self.is_active and self.username else self.id

    def resolve_role(self, info):
        return self.role

    def resolve_organization_id(self, info):
        return self.organization_id

    def resolve_last_activity_date(self, info):
        return self.last_login

    def resolve_status(self: User, info):
        return calculate_user_status(self)

    def resolve_all_permissions(self, info):
        all_permissions = {}

        for permission_name in self.get_all_permissions():
            application_name, permission = permission_name.split('.')
            if application_name not in all_permissions:
                all_permissions[application_name] = []
            all_permissions[application_name].append(permission)
        return [
            PermissionType(id=id, application_name=p[0], permissions=p[1])
            # we need to need to generate a fake id due to apollo
            # client to not mess with it's cache
            for id, p in enumerate(all_permissions.items())
        ]

    def resolve_profile_picture(self, info):
        if self.profile_picture:
            return ProfilePictureType(
                id=f'{self.id}_picture', url=self.profile_picture.url
            )
        return None

    def resolve_offboarding(self, info):
        try:
            return self.checklist_runs.get(
                checklist__action_item__name=ACTION_ITEM_OFFBOARDING
            )
        except Exception:
            return None

    def resolve_policies_reviewed_data(self, info):
        return ActionItem.objects.filter(assignees=self, metadata__type=TYPE_POLICY)

    def resolve_help_center_hash(self, info):
        user_id = self.username if self.is_active and self.username else self.id
        return get_help_center_hash(str(user_id))


class UserResponseType(BaseResponseType):
    data = graphene.Field(UserType)


class AuditorUserResponseType(BaseResponseType):
    data = graphene.Field(UserType)
    audit_firm = graphene.String()


class UsersResponseType(BaseResponseType):
    data = graphene.List(UserType)
    permissions = graphene.List(graphene.String)
    pagination = graphene.Field(PaginationResponseType)


class DiscoveredUsersResponseType(UsersResponseType):
    pass


class OfficerType(DjangoObjectType):
    class Meta:
        model = Officer
        fields = ('id', 'name', 'description', 'created_at', 'updated_at')

    user_details = graphene.Field(UserType)

    def resolve_user_details(self, info):
        return self.user


class DownloadLinkType(graphene.ObjectType):
    link = graphene.String(required=True)


class ExportResponseType(graphene.ObjectType):
    data = graphene.Field(DownloadLinkType)


class HtmlResponseType(graphene.ObjectType):
    html = graphene.String(required=True)


class TeamMemberType(DjangoObjectType):
    class Meta:
        model = TeamMember
        fields = ('id', 'phone', 'role', 'created_at', 'updated_at')

    user_details = graphene.Field(UserType)
    role = graphene.String()

    def resolve_user_details(self, info):
        return self.user

    def resolve_role(self, info):
        return self.role


class TeamType(DjangoObjectType):
    class Meta:
        model = Team
        fields = (
            'id',
            'name',
            'description',
            'notes',
            'charter',
            'created_at',
            'updated_at',
        )

    members = graphene.List(TeamMemberType)
    charter = graphene.String()
    notes = graphene.String()

    def resolve_members(self, info):
        return self.members.all()

    def resolve_charter(self, info):
        return self.charter

    def resolve_notes(self, info):
        return self.notes


class TeamResponseType(graphene.ObjectType):
    data = graphene.Field(TeamType)


class TeamsHtmlDataType(graphene.ObjectType):
    html = graphene.String(required=True)
    id = graphene.UUID(required=True)
    name = graphene.String(required=True)


class TeamsHtmlResponseType(graphene.ObjectType):
    data = graphene.List(TeamsHtmlDataType)


class UserFilterInputType(graphene.InputObjectType):
    exclude_roles = graphene.List(graphene.String)
    exclude_emails = graphene.List(graphene.String)
    roles_in = graphene.List(graphene.String)
    organization_id = graphene.String()


class AllUsersType(graphene.ObjectType):
    users = graphene.List(UserType)


class UserIncredibleFilterInputType(graphene.InputObjectType):
    field = graphene.String(required=True)
    value = graphene.String()
    operator = graphene.String(required=True)


class PartnerType(DjangoObjectType):
    class Meta:
        model = Partner
        fields = ('id', 'name')

    id = graphene.String()
    name = graphene.String()

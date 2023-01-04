import graphene

from laika import types
from user.models import Officer, Team, TeamMember


class UserInput(graphene.InputObjectType):
    email = graphene.String(required=True)
    id = graphene.String()
    role = graphene.String()
    last_name = graphene.String()
    first_name = graphene.String()
    username = graphene.String()
    email_preference = graphene.String()
    alert_preference = graphene.String()
    user_preferences = graphene.JSONString()
    phone_number = graphene.String()
    title = graphene.String()
    department = graphene.String()
    employment_type = graphene.String()
    employment_subtype = graphene.String()
    background_check_status = graphene.String()
    background_check_passed_on = graphene.Date()
    start_date = graphene.Date()
    end_date = graphene.Date()
    employment_status = graphene.String()
    manager_email = graphene.String()
    status = graphene.String()
    security_training = graphene.Boolean()


class UserInputEmail(graphene.InputObjectType):
    currentEmail = graphene.String(required=True)
    newEmail = graphene.String(required=True)


class InviteToOrganizationInput(UserInput):
    role = graphene.String()
    email = graphene.String(required=True)
    last_name = graphene.String(required=True)
    first_name = graphene.String(required=True)
    organization_id = graphene.UUID(required=True)
    partial = graphene.Boolean()
    user_preferences = graphene.JSONString()
    message = graphene.String(default_value='')
    show_inviter_name = graphene.Boolean(default_value=False)


class OfficerInput(object):
    id = graphene.UUID()
    name = graphene.String()
    user_email = graphene.String()
    description = graphene.String()


class CreateOfficerInput(OfficerInput, types.DjangoInputObjectBaseType):
    name = graphene.String(required=True)
    description = graphene.String(required=True)

    class InputMeta:
        model = Officer


class DeleteInput(graphene.InputObjectType):
    id = graphene.UUID(required=True)


class UpdateOfficerInput(OfficerInput, types.DjangoInputObjectBaseType):
    id = graphene.UUID(required=True)

    class InputMeta:
        model = Officer


class TeamInput(object):
    name = graphene.String()
    notes = graphene.String()
    charter = graphene.String()
    description = graphene.String()


class CreateTeamInput(TeamInput, types.DjangoInputObjectBaseType):
    name = graphene.String(required=True)
    description = graphene.String(required=True)

    class InputMeta:
        model = Team


class UpdateTeamInput(TeamInput, types.DjangoInputObjectBaseType):
    id = graphene.UUID(required=True)
    charter = graphene.String()
    notes = graphene.String()

    class InputMeta:
        model = Team


class TeamMemberInput(object):
    team_id = graphene.UUID(required=True)
    user_email = graphene.String(required=True)
    phone = graphene.String(required=True)
    role = graphene.String(required=True)


class AddMemberInput(TeamMemberInput, types.DjangoInputObjectBaseType):
    class InputMeta:
        model = TeamMember


class UpdateUserPermissionInput(graphene.InputObjectType):
    emails = graphene.List(graphene.String, required=True)
    role = graphene.String(required=True)


class ConfirmUserPermissionInput(graphene.InputObjectType):
    email = graphene.String(required=True)
    role = graphene.String(required=True)


class DelegateUserIntegrationInput(graphene.InputObjectType):
    email = graphene.String(required=True)
    vendor_id = graphene.String(required=False)
    category = graphene.String(required=True)


class DelegateUninvitedUserIntegrationInput(graphene.InputObjectType):
    first_name = graphene.String(required=True)
    last_name = graphene.String(required=True)
    email = graphene.String(required=True)
    vendor_id = graphene.String(required=False)
    category = graphene.String(required=True)

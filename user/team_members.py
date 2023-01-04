import graphene
import reversion
from django.db import transaction

from laika.auth import login_required
from laika.utils.exceptions import ServiceException, service_exception
from laika.utils.history import create_revision
from user.inputs import AddMemberInput, DeleteInput
from user.models import Team, TeamMember, User
from user.types import TeamMemberType


class AddMember(graphene.Mutation):
    class Arguments:
        input = AddMemberInput(required=True)

    data = graphene.Field(TeamMemberType)

    @login_required
    @transaction.atomic
    @service_exception('Cannot create team member')
    @create_revision('Added member')
    def mutate(self, info, input):
        organization_id = info.context.user.organization_id
        user = User.objects.get(
            email=input.get('user_email'), organization_id=organization_id
        )

        member = TeamMember.objects.filter(
            user_id=user.id, team_id=input.get('team_id')
        )

        if member.exists():
            raise ServiceException('Member already exists')

        team = Team.objects.get(id=input.get('team_id'))

        team_member = input.to_model(user=user, team=team)

        return AddMember(data=team_member)


class DeleteMember(graphene.Mutation):
    class Arguments:
        input = DeleteInput(required=True)

    success = graphene.Boolean(default_value=True)

    @login_required
    @transaction.atomic
    @service_exception('Cannot delete team member')
    def mutate(self, info, input):
        id = input.get('id')
        organization_id = info.context.user.organization_id
        with reversion.create_revision():
            reversion.set_comment('Deleted member')
            reversion.set_user(info.context.user)

            TeamMember.objects.filter(
                id=id, team__organization_id=organization_id
            ).delete()
            return DeleteMember()


class Mutation(graphene.ObjectType):
    add_member = AddMember.Field()
    delete_member = DeleteMember.Field()

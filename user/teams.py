import graphene
import reversion
from django.db import transaction

from laika.auth import login_required
from laika.utils.exceptions import ServiceException, service_exception
from laika.utils.history import create_revision
from laika.utils.templates import render_template
from user.inputs import CreateTeamInput, DeleteInput, UpdateTeamInput
from user.models import Team
from user.types import TeamsHtmlResponseType, TeamType
from user.views import get_formatted_members


class CreateTeam(graphene.Mutation):
    class Arguments:
        input = CreateTeamInput(required=True)

    data = graphene.Field(TeamType)

    @login_required
    @transaction.atomic
    @service_exception('Cannot create team')
    @create_revision('Created team')
    def mutate(self, info, input):
        organization_id = info.context.user.organization_id
        team_exists = Team.objects.filter(
            name=input.get('name'), organization_id=organization_id
        ).exists()

        if team_exists:
            raise ServiceException('Team with that name already exists')

        team = input.to_model(organization_id=info.context.user.organization_id)
        return CreateTeam(data=team)


class UpdateTeam(graphene.Mutation):
    class Arguments:
        input = UpdateTeamInput(required=True)

    data = graphene.Field(TeamType)

    @login_required
    @transaction.atomic
    @service_exception('Cannot create team')
    @create_revision('Updated team')
    def mutate(self, info, input):
        id = input.get('id')
        organization_id = info.context.user.organization_id
        current_team = Team.objects.get(id=id, organization_id=organization_id)

        team = input.to_model(update=current_team)
        return UpdateTeam(data=team)


class DeleteTeam(graphene.Mutation):
    class Arguments:
        input = DeleteInput(required=True)

    success = graphene.Boolean(default_value=True)

    @login_required
    @transaction.atomic
    @service_exception('Cannot delete team')
    def mutate(self, info, input):
        id = input.get('id')
        organization_id = info.context.user.organization_id
        with reversion.create_revision():
            reversion.set_comment('Deleted team')
            reversion.set_user(info.context.user)

            Team.objects.filter(id=id, organization_id=organization_id).delete()
            return DeleteTeam()


class Mutation(graphene.ObjectType):
    create_team = CreateTeam.Field()
    update_team = UpdateTeam.Field()
    delete_team = DeleteTeam.Field()


class Query(object):
    team = graphene.Field(TeamType, id=graphene.UUID(required=True))
    # TODO remove this one once dataroom and policy are migrated
    # as it's used just for internal api calls
    teams_html = graphene.Field(
        TeamsHtmlResponseType,
        timezone=graphene.String(),
        ids=graphene.List(graphene.String),
    )

    @login_required
    @service_exception('Cannot get team')
    def resolve_team(self, info, **kwargs):
        id = kwargs.get('id')
        organization_id = info.context.user.organization_id

        return Team.objects.get(id=id, organization_id=organization_id)

    @login_required
    @service_exception('Cannot get teams htlm')
    def resolve_teams_html(self, info, **kwargs):
        organization_id = info.context.user.organization_id
        time_zone = kwargs.get('timezone')
        ids = kwargs.get('ids')

        data = []

        for id in ids:
            team = Team.objects.get(id=id, organization_id=organization_id)
            team_members = team.members.all()
            team_name = team.name.title()
            if team:
                html = render_template(
                    template='team/export_team.html',
                    context={
                        'team': {
                            'name': team_name,
                            'notes': team.notes,
                            'charter': team.charter,
                            'members': get_formatted_members(team_members),
                        },
                    },
                    time_zone=time_zone,
                )
                team_data = {'html': html, 'name': team_name, 'id': id}
                data.append(team_data)

        return TeamsHtmlResponseType(data=data)

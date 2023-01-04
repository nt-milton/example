import graphene
import reversion
from django.db import transaction

from laika.auth import login_required
from laika.utils.exceptions import ServiceException, service_exception
from laika.utils.history import create_revision
from laika.utils.templates import render_template
from user.inputs import CreateOfficerInput, DeleteInput, UpdateOfficerInput
from user.models import Officer, User
from user.types import HtmlResponseType, OfficerType
from user.views import get_email, get_full_name, get_initials


class CreateOfficer(graphene.Mutation):
    class Arguments:
        input = CreateOfficerInput(required=True)

    data = graphene.Field(OfficerType)
    success = graphene.Boolean(default_value=True)

    @login_required
    @transaction.atomic
    @service_exception('Cannot create officer')
    @create_revision('Created officer')
    def mutate(self, info, input):
        organization_id = info.context.user.organization_id
        officer_exists = Officer.objects.filter(
            name=input.get('name'), organization_id=organization_id
        ).exists()

        if officer_exists:
            raise ServiceException('Officer with that name already exists')

        user = None
        if input.get('user_email'):
            user = User.objects.get(
                email=input.get('user_email'), organization_id=organization_id
            )

        officer = input.to_model(
            user=user, organization_id=info.context.user.organization_id
        )
        return CreateOfficer(data=officer)


class DeleteOfficer(graphene.Mutation):
    class Arguments:
        input = DeleteInput(required=True)

    success = graphene.Boolean(default_value=True)

    @login_required
    @transaction.atomic
    @service_exception('Cannot delete officer')
    def mutate(self, info, input):
        id = input.get('id')
        organization_id = info.context.user.organization_id
        with reversion.create_revision():
            reversion.set_comment('Deleted officer')
            reversion.set_user(info.context.user)

            Officer.objects.filter(id=id, organization_id=organization_id).delete()
            return DeleteOfficer()


class UpdateOfficer(graphene.Mutation):
    class Arguments:
        input = UpdateOfficerInput(required=True)

    data = graphene.Field(OfficerType)

    @login_required
    @transaction.atomic
    @service_exception('Cannot update officer')
    @create_revision('Updated officer')
    def mutate(self, info, input):
        organization_id = info.context.user.organization_id
        id = input.get('id')

        current_officer = Officer.objects.get(id=id, organization_id=organization_id)

        name = input.get('name')
        if name and name != current_officer.name:
            officer_with_name_exists = Officer.objects.filter(
                name=input.get('name'), organization_id=organization_id
            ).exists()

            if officer_with_name_exists:
                raise ServiceException('Officer with that name already exists')

        user = None
        if input.get('user_email'):
            user = User.objects.get(
                email=input.get('user_email'), organization_id=organization_id
            )

        current_officer.user = user
        officer = input.to_model(update=current_officer)

        return CreateOfficer(data=officer)


class Mutation(graphene.ObjectType):
    create_officer = CreateOfficer.Field()
    delete_officer = DeleteOfficer.Field()
    update_officer = UpdateOfficer.Field()


class Query(object):
    # TODO remove this one once dataroom and policy are migrated
    # as it's used just for internal api calls
    officers_html = graphene.Field(HtmlResponseType, timezone=graphene.String())

    @login_required
    @service_exception('Cannot get officers htlm')
    def resolve_officers_html(self, info, **kwargs):
        time_zone = kwargs.get('timezone')
        officers = info.context.user.organization.officers.all()

        html = render_template(
            template='officer/export_officers.html',
            context={
                'officers': [
                    {
                        'full_name': get_full_name(o.user),
                        'initials': get_initials(o.user),
                        'name': o.name,
                        'description': o.description,
                        'email': get_email(o.user),
                    }
                    for o in officers
                ]
            },
            time_zone=time_zone,
        )
        return HtmlResponseType(html=html)

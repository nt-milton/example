import base64
import io
import logging

import graphene
from django.core.files import File
from graphene_django.types import DjangoObjectType

from laika import types
from laika.auth import login_required
from laika.decorators import concierge_service
from laika.settings import CONCIERGE_SLACK_CHANNEL, DJANGO_SETTINGS, ORIGIN_LOCALHOST
from laika.utils import slack
from laika.utils.exceptions import service_exception

from .models import DEFAULT_PROGRESS_OPTION, ConciergeRequest

logger = logging.getLogger('concierge')


class ConciergeRequestType(DjangoObjectType):
    class Meta:
        model = ConciergeRequest

    file = graphene.Field(types.FileType)

    def resolve_file(self, info):
        if not self.file:
            return None

        return types.FileType(name=self.file.name, url=self.file.url)


class Query(object):
    concierge_requests = graphene.List(ConciergeRequestType)
    # TODO: Remove - For testing porpuses only
    concierge_list = graphene.String()

    @login_required
    @service_exception('Cannot get concierge requests')
    def resolve_concierge_requests(self, info, **kwargs):
        return ConciergeRequest.objects.filter(
            organization=info.context.user.organization
        ).exclude(request_type__in='request_unlock')

    # TODO: Remove - For testing porpuses only
    @concierge_service(
        permission='user.view_concierge',
        exception_msg='Failed to retrieve the concierge list',
        revision_name='Can view concierge',
    )
    def resolve_concierge_list(self, info, **kwargs):
        return 'Concierge List'


class ConciergeRequestInput(types.DjangoInputObjectBaseType):
    request_type = graphene.String(required=True)
    description = graphene.String(required=True)
    filename = graphene.String()
    contents = graphene.String()
    additional_information = graphene.String()

    class InputMeta:
        model = ConciergeRequest


class CreateConciergeRequest(graphene.Mutation):
    class Arguments:
        input = ConciergeRequestInput(required=True)

    concierge_request = graphene.Field(ConciergeRequestType)

    @login_required
    @service_exception('Cannot create concierge request')
    def mutate(self, info, input):
        file = None

        if input.filename and input.contents:
            file = File(
                name=input.filename, file=io.BytesIO(base64.b64decode(input.contents))
            )

        request = input.to_model(
            organization=info.context.user.organization,
            created_by=info.context.user,
            request_type=input.request_type,
            status=DEFAULT_PROGRESS_OPTION,
            file=file,
        )

        laika_web_redirect = DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')
        redirect_to = laika_web_redirect or ORIGIN_LOCALHOST[2]

        message = (
            'New Concierge Request from '
            f'{info.context.user.get_full_name()} '
            f'at {info.context.user.organization.name}! '
            f'Email: {info.context.user.email } \n'
            f'Request type: {input.request_type} \n'
            f'Description: {input.description} \n'
            f'({redirect_to}/concierge?requestID={request.id})'
        )

        slack.post_message(text=message, channel=CONCIERGE_SLACK_CHANNEL)

        return CreateConciergeRequest(concierge_request=request)


class UpdateConciergeRequestInput(types.DjangoInputObjectBaseType):
    filename = graphene.String()
    contents = graphene.String()
    status = graphene.String()
    description = graphene.String()
    additional_information = graphene.String()

    class InputMeta:
        model = ConciergeRequest


class UpdateConciergeRequest(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        input = UpdateConciergeRequestInput(required=True)

    concierge_request = graphene.Field(ConciergeRequestType)

    @staticmethod
    @login_required
    @service_exception('Cannot update concierge request')
    def mutate(root, info, id, input=None):
        request = ConciergeRequest.objects.get(
            pk=id, organization=info.context.user.organization
        )
        request = input.to_model(update=request, save=False)

        if input.filename == '' and input.contents == '':
            request.file = None

        if input.filename and input.contents:
            request.file = File(
                name=input.filename, file=io.BytesIO(base64.b64decode(input.contents))
            )

        request.save()

        return UpdateConciergeRequest(concierge_request=request)


class Mutation(graphene.ObjectType):
    create_concierge_request = CreateConciergeRequest.Field()
    update_concierge_request = UpdateConciergeRequest.Field()

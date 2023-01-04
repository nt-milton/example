import logging

import graphene
from django.db.models import Q

from laika.backends.concierge_backend import ConciergeAuthenticationBackend
from laika.backends.laika_backend import AuthenticationBackend
from laika.decorators import service
from laika.utils.exceptions import ServiceException
from laika.utils.get_organization_by_user_type import get_organization_by_user_type
from tag.models import Tag
from tag.mutations import AddManualTag
from tag.types import TagsResponseType, TagType
from user.constants import CONCIERGE

logger = logging.getLogger('tag')


def get_filter_query(organization, filter_by):
    filter_query = Q(organization=organization)
    for field, value in filter_by.items():
        if field == 'manual':
            filter_query.add(Q(is_manual=value), Q.AND)
    return filter_query


class Mutation(graphene.ObjectType):
    add_manual_tag = AddManualTag.Field()


class Query(object):
    tags = graphene.Field(
        TagsResponseType,
        search_criteria=graphene.String(),
        filter=graphene.JSONString(required=False),
        organization_id=graphene.String(),
    )

    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'drive.view_driveevidence',
            },
        ],
        exception_msg='Failed to retrieve tag list',
    )
    def resolve_tags(self, info, **kwargs):
        search_criteria = kwargs.get('search_criteria')
        filter_by = kwargs.get('filter', {})
        user_role = info.context.user.role

        if user_role == CONCIERGE:
            organization_id = kwargs.get('organization_id')

            if not organization_id:
                raise ServiceException('Bad Request, some parameters are missed')

        else:
            organization_id = info.context.user.organization_id

        organization = get_organization_by_user_type(info.context.user, organization_id)

        filter_query = get_filter_query(organization, filter_by)

        if search_criteria:
            filter_query.add(Q(name__icontains=search_criteria), Q.AND)

        tag_data = Tag.objects.filter(filter_query)
        all_tags = []

        for tag in tag_data:
            all_tags.append(
                TagType(
                    id=tag.id,
                    name=tag.name,
                    organization_name=tag.organization.name,
                    is_manual=tag.is_manual,
                )
            )

        return TagsResponseType(all_tags)

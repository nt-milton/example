import logging

import graphene

from .mutations import UpdateLink

logger = logging.getLogger(__name__)


class Mutation(graphene.ObjectType):
    update_link = UpdateLink.Field()

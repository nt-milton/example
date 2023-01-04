import graphene

from laika.decorators import laika_service
from user.models import WatcherList
from user.watcher_list.mutations import SubscribeToWatcherList
from user.watcher_list.types import WatcherListType


class Query(object):
    watcher_list = graphene.Field(WatcherListType, id=graphene.ID())

    @laika_service(
        permission='user.view_user', exception_msg='Failed to load watcher list'
    )
    def resolve_watcher_list(self, info, **kwargs):
        organization = info.context.user.organization
        id = kwargs.get('id')
        return WatcherList.objects.get(id=id, organization=organization)


class Mutation(graphene.ObjectType):
    subscribe_to_watcher_list = SubscribeToWatcherList.Field()

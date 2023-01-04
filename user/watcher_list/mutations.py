import graphene

from laika.decorators import laika_service
from user.models import WatcherList
from user.types import UserType


class SubscribeToWatcherList(graphene.Mutation):
    id = graphene.ID()
    watchers = graphene.List(UserType)

    class Arguments:
        id = graphene.ID()

    @laika_service(
        permission='user.view_user', exception_msg='Failed to load watcher list'
    )
    def mutate(self, info, **kwargs):
        id = kwargs.get('id')
        current_user = info.context.user
        watcher_list = WatcherList.objects.get(
            id=id, organization=current_user.organization
        )
        users = watcher_list.users
        if users.filter(pk=current_user.id).exists():
            users.remove(current_user)
        else:
            users.add(current_user)
        return SubscribeToWatcherList(id=watcher_list.id, watchers=users.all())

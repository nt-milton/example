import graphene
from graphene_django.types import DjangoObjectType

from user.models import WatcherList
from user.types import UserType


class WatcherListType(DjangoObjectType):
    class Meta:
        model = WatcherList
        fields = ('id', 'name')

    watchers = graphene.List(UserType)

    def resolve_watchers(self, info):
        return self.users.all()

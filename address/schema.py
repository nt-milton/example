import graphene
from graphene_django.types import DjangoObjectType

from laika.decorators import concierge_service

from .models import Address


class AddressInput(graphene.InputObjectType):
    street1 = graphene.String(required=True)
    street2 = graphene.String()
    city = graphene.String(required=True)
    state = graphene.String(required=True)
    zip_code = graphene.String(required=True)
    country = graphene.String(required=True)


class AddressType(DjangoObjectType):
    class Meta:
        model = Address


class AddressResponseType(graphene.ObjectType):
    data = graphene.List(AddressType)


class Query(object):
    addresses = graphene.Field(AddressResponseType)

    @concierge_service(
        permission='user.view_concierge',
        exception_msg='Failed to retrieve the address list',
        revision_name='Can view concierge',
    )
    def resolve_addresses(self, info, **kwargs):
        addresses = Address.objects.all()
        return AddressResponseType(data=addresses)

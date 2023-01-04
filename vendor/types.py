import graphene
from graphene_django import DjangoObjectType

from objects.models import LaikaObject
from objects.system_types import USER


class VendorFilterItemType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()


class VendorFiltersType(graphene.ObjectType):
    id = graphene.String()
    category = graphene.String()
    items = graphene.List(VendorFilterItemType)


class VendorEvidenceType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    description = graphene.String()
    link = graphene.String()
    evidence_type = graphene.String()
    date = graphene.DateTime()
    linkable = graphene.Boolean()
    content_id = graphene.String()


class FiltersVendorType(graphene.InputObjectType):
    search = graphene.String()
    risk_rating = graphene.List(graphene.String)
    status = graphene.List(graphene.String)
    internal_stakeholders = graphene.List(graphene.String)
    financial_exposure = graphene.List(graphene.String)
    operational_exposure = graphene.List(graphene.String)
    data_exposure = graphene.List(graphene.String)


class ServiceAccountType(DjangoObjectType):
    class Meta:
        model = LaikaObject
        fields = ('id',)

    id = graphene.ID()
    username = graphene.String()
    connection = graphene.String()
    email = graphene.String()
    groups = graphene.String()

    def resolve_id(self, info):
        return self.id

    def resolve_username(self, info):
        if self.object_type.type_name == USER.type:
            return (
                f'{self.data.get("First Name", "")} {self.data.get("Last Name", "")}'
            ).strip()
        return self.data.get('Display Name', '')

    def resolve_connection(self, info):
        return self.connection_account.alias

    def resolve_email(self, info):
        return self.data.get('Email', '')

    def resolve_groups(self, info):
        if self.object_type.type_name == USER.type:
            return (
                f'{self.data.get("Groups", "")} {self.data.get("Roles", "")}'
            ).strip()
        return self.data.get('Roles', '')

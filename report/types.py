import graphene
from graphene_django.types import DjangoObjectType

from drive.types import SubItems
from laika.types import PaginationResponseType
from link.models import Link
from report.models import Report


class LinkType(DjangoObjectType):
    class Meta:
        model = Link
        fields = ('id', 'expiration_date', 'is_enabled', 'url')

    is_valid = graphene.Boolean()
    is_expired = graphene.Boolean()
    public_url = graphene.String()

    def resolve_is_valid(self, info):
        return self.is_valid

    def resolve_is_expired(self, info):
        return self.is_expired

    def resolve_public_url(self, info):
        return self.public_url


class ReportType(DjangoObjectType):
    class Meta:
        model = Report

    display_id = graphene.String()
    link = graphene.Field(LinkType)

    def resolve_display_id(self, info):
        return f'CR-{self.display_id}'

    def resolve_link(self, info, **kwargs):
        return self.link


class ReportsResponseType(graphene.ObjectType):
    data = graphene.List(ReportType)
    pagination = graphene.Field(PaginationResponseType)


class ReportResponseType(graphene.ObjectType):
    data = graphene.Field(ReportType)


class FilterItemsReports(graphene.ObjectType):
    id = graphene.String(required=True)
    name = graphene.String(required=True)
    sub_items = graphene.List(SubItems, default_value=[])
    disabled = graphene.Boolean(default_value=False)


class FilterGroupsReports(graphene.ObjectType):
    id = graphene.String(required=True)
    name = graphene.String(required=True)
    items = graphene.List(FilterItemsReports, default_value=[])

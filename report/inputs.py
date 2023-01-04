import graphene

from laika import types
from report.models import Report


class ReportInput(object):
    name = graphene.String(required=True)


class CreateReportInput(ReportInput, types.DjangoInputObjectBaseType):
    class InputMeta:
        model = Report


class ToggleReportInput(graphene.InputObjectType):
    report_id = graphene.String(required=True)
    value = graphene.Boolean(required=True)

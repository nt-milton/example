import graphene
from graphene_django import DjangoObjectType

from audit.models import DraftReportComment
from comment.types import AppCommentType


class DraftReportCommentType(DjangoObjectType):
    class Meta:
        model = DraftReportComment
        fields = ('id', 'page', 'is_latest_version', 'auditor_notified')

    comment = graphene.Field(AppCommentType)

    def resolve_comment(self, info):
        return self.comment

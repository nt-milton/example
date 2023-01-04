import graphene

from comment.inputs import CommentInput


class DraftReportCommentInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    comment_id = graphene.String(required=True)


class RunFetchEvidenceInput(graphene.InputObjectType):
    evidence_ids = graphene.List(graphene.String)
    audit_id = graphene.String(required=True)
    timezone = graphene.String()


class UpdateDraftReportCommentInput(
    CommentInput, DraftReportCommentInput, graphene.InputObjectType
):
    page = graphene.String()


class UpdateDraftReportCommentStateInput(
    DraftReportCommentInput, graphene.InputObjectType
):
    state = graphene.String(required=True)


class CreateAuditeeDraftReportReplyInput(CommentInput, graphene.InputObjectType):
    audit_id = graphene.String(required=True)
    comment_id = graphene.String(required=True)


class UpdateAuditeeDraftReportReplyInput(
    CommentInput, DraftReportCommentInput, graphene.InputObjectType
):
    reply_id = graphene.String(required=True)


class DeleteAuditeeDraftReportReplyInput(
    DraftReportCommentInput, graphene.InputObjectType
):
    reply_id = graphene.String(required=True)


class CreateNotificationReviewedDraftReportInput(graphene.InputObjectType):
    audit_id = graphene.String(required=True)
